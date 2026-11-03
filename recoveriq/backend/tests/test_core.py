import json
import uuid

import pytest
from fastapi import HTTPException

from app.domain import rule_eval, scoring
from app.domain.state_machine import assert_transition
from app.integrations import gateway


# ---------------------------------------------------------------- pure domain

@pytest.mark.parametrize("expr", ["__import__('os').system('x')", "dpd.real", "open('x')", "[1][0]", "x > 1",
                                  "lambda: 1", "'a' == 'a'"])
def test_rule_evaluator_rejects_unsafe(expr):
    with pytest.raises(rule_eval.RuleError):
        rule_eval.compile_rule(expr)


def test_rule_evaluator_evaluates():
    tree = rule_eval.compile_rule("missed_emis >= 3 or dpd > 90")
    case = type("C", (), {"missed_emis": 1, "dpd": 95})()
    assert rule_eval.evaluate(tree, case)
    case.dpd = 40
    assert not rule_eval.evaluate(tree, case)


def test_scorecard_reasons_add_up():
    from app.domain.rules import DEFAULTS
    case = type("C", (), dict(dpd=74, missed_emis=3, outstanding=250000, broken_ptp_count=2, unreachable_streak=3,
                             last_reason_category=None, last_collected_at=None, kept_ptp_count=0, amount_due=30000))()
    score, reasons = scoring.scorecard(case, DEFAULTS["scoring"])
    assert score == sum(r["points"] for r in reasons) == 25 + 15 + 5 + 10 + 10
    assert scoring.decide_channel(case, score, DEFAULTS["channel"]) == "FIELD"


def test_paid_only_from_gateway():
    with pytest.raises(HTTPException):
        assert_transition("FIELD", "PAID", "user")
    assert_transition("PAYMENT_PENDING", "PAID", "gateway")


# ---------------------------------------------------------------- API

def first_case(client, headers, **params):
    r = client.get("/api/v1/cases", params={"limit": 50, **params}, headers=headers)
    assert r.status_code == 200
    return r.json()["items"]


def test_pii_masked_and_reveal_audited(client, execu):
    c = first_case(client, execu)[0]
    d = client.get(f"/api/v1/cases/{c['id']}", headers=execu).json()
    assert "X" in d["phone"] and d["phone_for_call"] is None
    r = client.post(f"/api/v1/cases/{c['id']}/reveal-pii", json={"reason": "x"}, headers=execu)
    assert r.status_code == 422
    r = client.post(f"/api/v1/cases/{c['id']}/reveal-pii", json={"reason": "Borrower called the helpline"}, headers=execu)
    assert r.status_code == 200 and r.json()["phone"].startswith("+91")
    log = client.get("/api/v1/audit", params={"action": "pii.reveal"}, headers=execu).json()
    assert log["items"][0]["payload"]["reason"] == "Borrower called the helpline"


def test_agent_scope_isolation(client, agent, admin):
    mine = {c["id"] for c in client.get("/api/v1/agent/worklist", headers=agent).json()["items"]}
    other = next(c for c in first_case(client, admin, limit=200) if c["id"] not in mine)
    assert client.get(f"/api/v1/cases/{other['id']}", headers=agent).status_code == 404


def test_sync_push_is_idempotent(client, agent):
    case = client.get("/api/v1/agent/worklist", headers=agent).json()["items"][0]
    op = {"client_id": str(uuid.uuid4()), "type": "visit", "case_id": case["id"],
          "data": {"lat": case["lat"] + 0.0005, "lng": case["lng"], "accuracy_m": 12, "outcome": "met_borrower"}}
    r1 = client.post("/api/v1/sync/push", json={"ops": [op]}, headers=agent).json()
    r2 = client.post("/api/v1/sync/push", json={"ops": [op]}, headers=agent).json()
    assert r1["results"][0]["status"] == "applied"
    assert r2["results"][0]["status"] == "duplicate"
    detail = client.get(f"/api/v1/cases/{case['id']}", headers=agent).json()
    assert sum(1 for v in detail["visits"] if v["distance_m"] < 100) >= 1


def test_webhook_signature_and_no_double_posting(client, agent, admin):
    case = next(c for c in client.get("/api/v1/agent/worklist", headers=agent).json()["items"]
                if c["status"] not in ("PAID", "DISPUTED") and c["amount_due"] > 100)
    link = client.post(f"/api/v1/cases/{case['id']}/payment-link", json={"amount": 100}, headers=agent).json()
    assert client.post(f"/api/v1/public/pay/{link['token']}/checkout").status_code == 200
    detail = client.get(f"/api/v1/cases/{case['id']}", headers=agent).json()
    assert detail["status"] == "PAYMENT_PENDING"
    body = gateway.build_webhook("payment_link.paid",
                                 {"id": link["gateway_link_id"], "amount": 100, "amount_paid": 100, "status": "paid",
                                  "reference_id": case["account_no"]},
                                 {"id": "pay_test_" + uuid.uuid4().hex[:8], "amount": 100, "status": "captured", "method": "upi"})
    bad = client.post("/api/v1/webhooks/razorpay", content=body, headers={"X-Razorpay-Signature": "0" * 64})
    assert bad.status_code == 401
    ok = client.post("/api/v1/webhooks/razorpay", content=body, headers={"X-Razorpay-Signature": gateway.sign(body)})
    assert ok.status_code == 200 and ok.json()["result"] == "posted"
    dup = client.post("/api/v1/webhooks/razorpay", content=body, headers={"X-Razorpay-Signature": gateway.sign(body)})
    assert dup.json()["result"] == "duplicate_ignored"
    pays = client.get(f"/api/v1/cases/{case['id']}", headers=agent).json()["payments"]
    assert sum(1 for p in pays if p["gateway_payment_id"] == json.loads(body)["payload"]["payment"]["entity"]["id"]) == 1


def test_quiet_hours_block_nudge(client, l2):
    case = first_case(client, l2, channel="DIGITAL", status="DIGITAL")[0]
    client.post("/api/v1/clock", json={"mode": "set_local_time", "time": "20:30"}, headers=l2)
    r = client.post(f"/api/v1/cases/{case['id']}/nudge", json={"channel": "sms"}, headers=l2).json()
    assert r["sent"] is False and "Quiet hours" in r["reason"]
    client.post("/api/v1/clock", json={"mode": "set_local_time", "time": "11:00"}, headers=l2)
    r = client.post(f"/api/v1/cases/{case['id']}/nudge", json={"channel": "email"}, headers=l2).json()
    assert r["sent"] is True and "/p/" in r["text"]
    client.post("/api/v1/clock", json={"mode": "reset"}, headers=l2)


def test_intake_dedupes(client, admin):
    sample = client.get("/api/v1/intake/sample.csv", headers=admin).content
    r1 = client.post("/api/v1/intake/upload", files={"file": ("s.csv", sample, "text/csv")}, headers=admin).json()
    r2 = client.post("/api/v1/intake/upload", files={"file": ("s.csv", sample, "text/csv")}, headers=admin).json()
    assert r1["created"] == 6 and r1["rejected"] == 1
    assert r2["created"] == 0 and r2["unchanged"] == 6


def test_audit_chain_detects_tamper(client, admin):
    assert client.get("/api/v1/audit/verify", headers=admin).json()["ok"]
    t = client.post("/api/v1/audit/demo/tamper", headers=admin).json()
    v = client.get("/api/v1/audit/verify", headers=admin).json()
    assert not v["ok"] and v["broken_at"] == t["tampered_row"]
    client.post("/api/v1/audit/demo/restore", headers=admin)
    assert client.get("/api/v1/audit/verify", headers=admin).json()["ok"]


def test_ptp_breaks_after_grace(client, agent, l2):
    case = next(c for c in client.get("/api/v1/agent/worklist", headers=agent).json()["items"]
                if c["status"] in ("FIELD", "TELE"))
    from datetime import date, timedelta
    r = client.post(f"/api/v1/cases/{case['id']}/promises", headers=agent,
                    json={"client_id": str(uuid.uuid4()), "amount": 500, "promised_date": (date.today() + timedelta(days=1)).isoformat()})
    assert r.status_code == 200
    out = client.post("/api/v1/clock", json={"mode": "advance_days", "value": 4}, headers=l2).json()
    assert out["promises_broken"] >= 1
    d = client.get(f"/api/v1/cases/{case['id']}", headers=l2).json()
    assert any(p["status"] == "broken" for p in d["promises"])
    client.post("/api/v1/clock", json={"mode": "reset"}, headers=l2)


def test_rule_change_reroutes(client, admin):
    rules = client.get("/api/v1/rules", headers=admin).json()["channel"]["active"]["definition"]
    r = client.put("/api/v1/rules/channel", headers=admin,
                   json={"definition": {**rules, "field_score": 55}, "note": "test lower field threshold"}).json()
    assert r["version"] >= 2 and r["impact"]["rerouted"] >= 1
    client.put("/api/v1/rules/channel", headers=admin, json={"definition": rules, "note": "restore"})


def test_learning_loop(client, admin):
    m = client.post("/api/v1/models/retrain", headers=admin).json()
    assert m["status"] == "shadow" and m["metrics"]["auc"] > 0.6
    a = client.post(f"/api/v1/models/{m['id']}/approve", headers=admin).json()
    assert a["activated"] == m["version"]


def test_login_lockout(client):
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": "l1.east@recoveriq.in", "password": "wrong"})
    r = client.post("/api/v1/auth/login", json={"email": "l1.east@recoveriq.in", "password": "Demo@1234"})
    assert r.status_code == 423


def test_no_contact_delivered_outside_window(client, admin):
    r = client.get("/api/v1/compliance/report", params={"days": 30}, headers=admin).json()
    assert r["total_attempts"] > 0 and r["delivered_outside_window"] == 0
