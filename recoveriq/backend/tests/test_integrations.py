"""Integrations that need outside accounts, tested against mocked provider APIs."""
import json
import uuid

import httpx
import pytest

from app.config import settings
from app.domain.sentiment import analyse
from app.integrations import gateway, messaging


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


# ---------------------------------------------------------------- offline gist
def test_marathi_and_hindi_gist():
    r = analyse("नोकरी गेली आहे, पगार आल्यावर पुढच्या महिन्यात हप्ता भरेन.")
    assert r["language"] == "mr" and r["reason_category"] == "will_pay"
    assert "lost the job" in r["english_text"].lower() and "will pay" in r["english_text"]
    r = analyse("पैसा नहीं दूंगा, जो करना है करो।")
    assert r["sentiment"] == "negative" and "will not pay" in r["english_text"].lower()


# ---------------------------------------------------------------- Twilio / SMTP
def test_messaging_inactive_without_config(monkeypatch):
    for k in ("TWILIO_ACCOUNT_SID", "SMTP_HOST", "DEMO_RECIPIENT_PHONE", "DEMO_RECIPIENT_EMAIL"):
        monkeypatch.delenv(k, raising=False)
    assert messaging.send("sms", "hi") == {"provider": None, "ok": True}


def test_twilio_sms_and_whatsapp(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setenv("TWILIO_SMS_FROM", "+15005550006")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "+14155238886")
    monkeypatch.setenv("DEMO_RECIPIENT_PHONE", "+919800000000")
    calls = []

    def fake_post(url, data=None, auth=None, timeout=None):
        calls.append((url, data, auth))
        return Resp(201, {"sid": "SM123"})
    monkeypatch.setattr(messaging.httpx, "post", fake_post)
    assert messaging.send("sms", "pay")["id"] == "SM123"
    assert calls[0][0].endswith("/Accounts/ACtest/Messages.json") and calls[0][1]["To"] == "+919800000000"
    messaging.send("whatsapp", "pay")
    assert calls[1][1]["To"] == "whatsapp:+919800000000" and calls[1][1]["From"] == "whatsapp:+14155238886"
    monkeypatch.setattr(messaging.httpx, "post", lambda *a, **k: Resp(400, {"message": "Unverified number"}))
    r = messaging.send("sms", "pay")
    assert r["ok"] is False and "Unverified" in r["error"]


def test_smtp_email(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_FROM", "collections@test")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("DEMO_RECIPIENT_EMAIL", "me@test")
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None): sent["host"] = (host, port)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): sent["tls"] = True
        def login(self, u, p): sent["login"] = u
        def send_message(self, m): sent["to"] = m["To"]
    monkeypatch.setattr(messaging.smtplib, "SMTP", FakeSMTP)
    assert messaging.send("email", "hello")["ok"]
    assert sent == {"host": ("smtp.test", 587), "tls": True, "login": "u", "to": "me@test"}


# ---------------------------------------------------------------- Razorpay
def test_razorpay_link_and_reconciliation(monkeypatch, client, agent, admin):
    monkeypatch.setattr(type(settings), "razorpay_key_id", "rzp_test_x", raising=False)
    monkeypatch.setattr(type(settings), "razorpay_key_secret", "secret", raising=False)
    assert settings.gateway == "razorpay"
    seen = {}

    def fake_post(url, json=None, auth=None, timeout=None):
        seen["create"] = (url, json, auth)
        return Resp(200, {"id": "plink_RZP" + uuid.uuid4().hex[:6], "short_url": "https://rzp.io/i/abc"})
    monkeypatch.setattr(gateway.httpx, "post", fake_post)
    case = next(c for c in client.get("/api/v1/agent/worklist", headers=agent).json()["items"]
                if c["status"] not in ("PAID", "DISPUTED", "PAYMENT_PENDING") and c["amount_due"] > 300)
    link = client.post(f"/api/v1/cases/{case['id']}/payment-link", json={"amount": 300}, headers=agent).json()
    url, body, auth = seen["create"]
    assert url == "https://api.razorpay.com/v1/payment_links" and body["amount"] == 30000 and body["currency"] == "INR"
    assert auth == ("rzp_test_x", "secret") and link["gateway"] == "razorpay"
    co = client.post(f"/api/v1/public/pay/{link['token']}/checkout").json()
    assert co["checkout_url"] == "https://rzp.io/i/abc"

    # webhook never arrives -> reconciliation asks Razorpay
    pay_id = "pay_RZP" + uuid.uuid4().hex[:8]
    monkeypatch.setattr(gateway.httpx, "get", lambda url, auth=None, timeout=None:
                        Resp(200, {"payments": [{"payment_id": pay_id, "amount": 30000, "status": "captured", "method": "upi"}]}))
    r = client.post("/api/v1/payments/reconcile", headers=admin).json()
    assert r["posted"] >= 1
    pays = client.get(f"/api/v1/cases/{case['id']}", headers=agent).json()["payments"]
    assert any(p["gateway_payment_id"] == pay_id and p["source"] == "reconciliation" for p in pays)
    # a late webhook for the same payment is ignored (no double posting)
    raw = gateway.build_webhook("payment_link.paid", {"id": link["gateway_link_id"], "amount": 300, "amount_paid": 300,
                                                      "status": "paid", "reference_id": case["account_no"]},
                                {"id": pay_id, "amount": 300, "status": "captured", "method": "upi"})
    res = client.post("/api/v1/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": gateway.sign(raw)})
    assert res.json()["result"] == "duplicate_ignored"
