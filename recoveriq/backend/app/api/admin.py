from __future__ import annotations

import copy
import os
import json
import socket
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import audit, clock
from ..config import settings
from ..db import AUDIT_TRIGGERS, get_db, get_write_db
from ..domain import ml, rule_eval, rules as rulebook
from ..domain.state_machine import WORKING
from ..integrations import llm
from ..models import (
    AuditLog, Case, ContactAttempt, Dispute, ModelVersion, Promise, RuleVersion, User, Visit,
)
from ..security import MANAGERS, ROLE_LABEL, current_user, require
from ..services import (
    add_event, break_due_promises, clear_model_cache, paid_recently, rescore, set_status, touch,
)
from .deps import client_ip, iso, local_str, scope_filter

router = APIRouter(tags=["admin"])


# ------------------------------------------------------------------ meta (public)

def lan_ips() -> list[str]:
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(ips)


@router.get("/meta")
def meta():
    return {"app": "RecoverIQ", "version": "1.0.0", "gateway": settings.gateway, "llm": llm.available(),
            "llm_model": settings.llm_model if llm.available() else None, "demo_mode": settings.demo_mode,
            "lan_ips": lan_ips(), "port": settings.port, "https_port": int(os.getenv("HTTPS_PORT", "0")) or None, "timezone": settings.timezone,
            "clock": {"now": iso(clock.utcnow()), "local": clock.local_now().strftime("%a %d %b %Y, %H:%M"),
                      "offset_seconds": clock.get_offset()}}


# ------------------------------------------------------------------ demo clock

class ClockIn(BaseModel):
    mode: str  # reset | advance_hours | advance_days | set_local_time
    value: float | None = None
    time: str | None = None  # HH:MM for set_local_time


@router.post("/clock")
def set_clock(body: ClockIn, user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_write_db, scope="function")):
    if not settings.demo_mode:
        raise HTTPException(403, "Demo clock is disabled")
    off = clock.get_offset()
    if body.mode == "reset":
        off = 0.0
    elif body.mode == "advance_hours":
        off += float(body.value or 1) * 3600
    elif body.mode == "advance_days":
        off += float(body.value or 1) * 86400
    elif body.mode == "set_local_time":
        try:
            hh, mm = map(int, (body.time or "").split(":"))
        except ValueError:
            raise HTTPException(422, "time must be HH:MM")
        now_local = clock.local_now()
        target = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
        off += (target - now_local).total_seconds()
    else:
        raise HTTPException(422, "Unknown mode")
    clock.set_offset(off)
    rulebook.put_setting(db, "clock_offset", off)
    audit.record(db, user, "clock.changed", "settings", "clock",
                 {"mode": body.mode, "value": body.value, "time": body.time, "offset_seconds": off})
    broken = break_due_promises(db)
    db.info.setdefault("events", []).append({"type": "clock.changed", "broadcast": True, "offset": off})
    return {"offset_seconds": off, "local": clock.local_now().strftime("%a %d %b %Y, %H:%M"), "promises_broken": broken}


@router.post("/scheduler/ptp")
def run_ptp(user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_write_db, scope="function")):
    return {"promises_broken": break_due_promises(db)}


# ------------------------------------------------------------------ users

@router.get("/users")
def users(role: str | None = None, user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_db)):
    q = select(User).order_by(User.role, User.name)
    if role:
        q = q.where(User.role == role)
    if user.role == "l2":
        q = q.where(User.branch_id == user.branch_id)
    elif user.role == "l1":
        q = q.where(User.region_id == user.region_id)
    return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "role_label": ROLE_LABEL[u.role],
             "branch": u.branch.name if u.branch else None, "branch_id": u.branch_id, "capacity": u.capacity,
             "active": u.active} for u in db.execute(q).scalars()]


# ------------------------------------------------------------------ rules

@router.get("/rules")
def get_rules(user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_db)):
    out = {}
    for kind in rulebook.DEFAULTS:
        act = rulebook.active(db, kind)
        hist = db.execute(select(RuleVersion).where(RuleVersion.kind == kind).order_by(RuleVersion.version.desc()).limit(10)).scalars()
        out[kind] = {"active": {"version": act.version, "definition": act.definition, "note": act.note,
                                "created_at": iso(act.created_at)},
                     "history": [{"version": r.version, "note": r.note, "active": r.active, "created_at": iso(r.created_at),
                                  "created_by": (db.get(User, r.created_by).name if r.created_by else "system")} for r in hist]}
    out["fields"] = rule_eval.FIELDS
    out["costs"] = rulebook.get_setting(db, "costs", rulebook.DEFAULT_COSTS)
    return out


class RuleIn(BaseModel):
    definition: dict
    note: str = Field(min_length=3, max_length=200)


def _validate(kind: str, d: dict) -> dict:
    base = rulebook.DEFAULTS[kind]
    if kind == "default":
        rule_eval.compile_rule(d.get("expression", ""))
        return {"expression": d["expression"].strip()}
    if kind == "channel":
        out = {k: float(d[k]) for k in base}
        if not 0 <= out["tele_score"] <= out["field_score"] <= 100:
            raise HTTPException(422, "Need 0 ≤ tele_score ≤ field_score ≤ 100")
        return out
    if kind == "priority":
        out = {k: float(d[k]) for k in base}
        if abs(out["w_risk"] + out["w_amount"] + out["w_dpd"] - 1) > 0.01:
            raise HTTPException(422, "Weights must add up to 1.0")
        return out
    if kind == "contact_policy":
        out = copy.deepcopy(d)
        for k in ("window_start", "window_end"):
            datetime.strptime(out[k], "%H:%M")
        if out["window_start"] >= out["window_end"]:
            raise HTTPException(422, "Window start must be before end")
        for ch, cap in out["caps"].items():
            if ch not in base["caps"] or int(cap["day"]) < 0 or int(cap["week"]) < int(cap["day"]):
                raise HTTPException(422, f"Invalid cap for {ch}")
        return out
    if kind == "scoring":
        out = copy.deepcopy(base)
        for k, v in d.items():
            if k in out:
                out[k] = v
        return out
    raise HTTPException(404, "Unknown rule kind")


def rescore_all(db: Session, user: User | None, route: bool = True) -> dict:
    moved = {"FIELD": 0, "TELE": 0, "DIGITAL": 0}
    changed = 0
    defaults = 0
    for case in db.execute(select(Case).where(Case.status.notin_(("CLOSED",)))).scalars():
        before = (case.channel, case.is_default)
        rescore(db, case, user, route=route)
        if case.channel != before[0]:
            changed += 1
            moved[case.channel] = moved.get(case.channel, 0) + 1
            touch(db, case, "case.rerouted")
        if case.is_default and not before[1]:
            defaults += 1
    return {"rerouted": changed, "to": moved, "new_defaults": defaults}


@router.put("/rules/{kind}")
def put_rule(kind: str, body: RuleIn, request: Request, user: User = Depends(require("admin", "l1")),
             db: Session = Depends(get_write_db, scope="function")):
    if kind not in rulebook.DEFAULTS:
        raise HTTPException(404, "Unknown rule kind")
    try:
        definition = _validate(kind, body.definition)
    except rule_eval.RuleError as e:
        raise HTTPException(422, str(e))
    except (KeyError, ValueError, TypeError) as e:
        raise HTTPException(422, f"Invalid definition: {e}")
    prev = rulebook.active(db, kind)
    row = rulebook.publish(db, kind, definition, user.id, body.note)
    audit.record(db, user, "rules.published", "rule", row.id,
                 {"kind": kind, "version": row.version, "from": prev.definition, "to": definition, "note": body.note},
                 client_ip(request))
    impact = rescore_all(db, user) if kind in ("scoring", "channel", "priority", "default") else {}
    from ..services import allocate
    from ..models import Branch
    if impact.get("rerouted"):
        impact["auto_assigned"] = allocate(db, list(db.execute(select(Branch.id)).scalars()), user)["assigned"]
    return {"version": row.version, "impact": impact}


class TestRuleIn(BaseModel):
    expression: str


@router.post("/rules/default/test")
def test_default_rule(body: TestRuleIn, user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_db)):
    try:
        tree = rule_eval.compile_rule(body.expression)
    except rule_eval.RuleError as e:
        raise HTTPException(422, str(e))
    cases = db.execute(select(Case).where(Case.status.notin_(("PAID", "CLOSED")))).scalars().all()
    hits = [c for c in cases if rule_eval.evaluate(tree, c)]
    return {"matches": len(hits), "of": len(cases), "sample": [c.account_no for c in hits[:8]]}


class CostsIn(BaseModel):
    visit: float
    call: float
    sms: float
    whatsapp: float
    email: float


@router.put("/settings/costs")
def put_costs(body: CostsIn, user: User = Depends(require("admin", "exec")), db: Session = Depends(get_write_db, scope="function")):
    rulebook.put_setting(db, "costs", body.model_dump())
    audit.record(db, user, "settings.costs", "settings", "costs", body.model_dump())
    return body.model_dump()


# ------------------------------------------------------------------ learning loop

def model_out(db: Session, m: ModelVersion) -> dict:
    coef = dict(zip(m.params["features"], m.params["coef"]))
    return {"id": m.id, "version": m.version, "name": m.name, "status": m.status, "metrics": m.metrics,
            "training_rows": m.training_rows, "real_outcome_rows": m.real_outcome_rows, "created_at": iso(m.created_at),
            "approved_by": db.get(User, m.approved_by).name if m.approved_by else None, "approved_at": iso(m.approved_at),
            "weights": sorted([{"feature": k, "label": ml.LABELS.get(k, k), "coef": round(v, 3)} for k, v in coef.items()],
                              key=lambda r: -abs(r["coef"]))}


@router.get("/models")
def models(user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_db)):
    rows = db.execute(select(ModelVersion).order_by(ModelVersion.version.desc())).scalars().all()
    shadow = next((m for m in rows if m.status == "shadow"), None)
    active = next((m for m in rows if m.status == "active"), None)
    comparison = []
    if shadow and active:
        sample = db.execute(select(Case).where(Case.status.notin_(("PAID", "CLOSED"))).order_by(Case.priority.desc()).limit(12)).scalars()
        for c in sample:
            x = ml.case_features(c, paid_recently(c))
            pa, _ = ml.predict(active.params, x)
            ps, _ = ml.predict(shadow.params, x)
            comparison.append({"account_no": c.account_no, "case_id": c.id, "active": pa, "shadow": ps, "delta": round(ps - pa, 4)})
    return {"models": [model_out(db, m) for m in rows], "shadow_comparison": comparison,
            "note": "Prototype models are trained on documented synthetic data plus outcomes recorded in this system."}


def _real_outcomes(db: Session):
    X, y = [], []
    for c in db.execute(select(Case).where(Case.status.in_(("PAID", "CLOSED", "BROKEN_PTP", "ESCALATED")))).scalars():
        X.append(ml.case_features(c, paid_recently(c)))
        y.append(1 if c.status in ("PAID", "CLOSED") else 0)
    return X, y


@router.post("/models/retrain")
def retrain(user: User = Depends(require("admin", "l1", "exec")), db: Session = Depends(get_write_db, scope="function")):
    X, y = _real_outcomes(db)
    version = (db.execute(select(func.max(ModelVersion.version))).scalar() or 0) + 1
    res = ml.train(X or None, y or None, seed=7 + version)
    for old in db.execute(select(ModelVersion).where(ModelVersion.status == "shadow")).scalars():
        old.status = "retired"
    m = ModelVersion(version=version, name=f"selfcure-logreg-v{version}", status="shadow", params=res["params"],
                     metrics=res["metrics"], training_rows=res["training_rows"], real_outcome_rows=res["real_outcome_rows"],
                     created_at=clock.utcnow())
    db.add(m)
    db.flush()
    audit.record(db, user, "model.trained", "model", m.id, {"version": version, "metrics": res["metrics"],
                                                            "real_outcome_rows": res["real_outcome_rows"]})
    return model_out(db, m)


@router.post("/models/{model_id}/approve")
def approve(model_id: str, user: User = Depends(require("admin", "l1", "exec")), db: Session = Depends(get_write_db, scope="function")):
    m = db.get(ModelVersion, model_id)
    if not m or m.status not in ("shadow", "retired"):
        raise HTTPException(409, "Only a shadow or retired model can be activated")
    prev = db.execute(select(ModelVersion).where(ModelVersion.status == "active")).scalar()
    if prev:
        prev.status = "retired"
    m.status, m.approved_by, m.approved_at = "active", user.id, clock.utcnow()
    db.flush()
    clear_model_cache()
    audit.record(db, user, "model.activated", "model", m.id,
                 {"version": m.version, "replaced": prev.version if prev else None, "rollback": m.approved_at is not None})
    impact = rescore_all(db, user, route=False)
    return {"activated": m.version, "replaced": prev.version if prev else None, "rescored": True, **impact}


# ------------------------------------------------------------------ audit

@router.get("/audit")
def audit_list(action: str | None = None, entity: str | None = None, q: str | None = None, limit: int = 100,
               before_id: int | None = None, user: User = Depends(require("l1", "exec", "admin")),
               db: Session = Depends(get_db)):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if q:
        stmt = stmt.where(AuditLog.payload.like(f"%{q}%") | AuditLog.actor_name.like(f"%{q}%"))
    if before_id:
        stmt = stmt.where(AuditLog.id < before_id)
    rows = db.execute(stmt.order_by(AuditLog.id.desc()).limit(min(limit, 300))).scalars().all()
    total = db.execute(select(func.count()).select_from(AuditLog)).scalar()
    actions = [a for (a,) in db.execute(select(AuditLog.action).distinct().order_by(AuditLog.action)).all()]
    return {"total": total, "actions": actions,
            "items": [{"id": r.id, "ts": iso(r.ts), "ts_local": local_str(r.ts), "actor": r.actor_name, "role": r.role,
                       "action": r.action, "entity": r.entity, "entity_id": r.entity_id, "payload": json.loads(r.payload),
                       "ip": r.ip, "prev_hash": r.prev_hash, "hash": r.hash} for r in rows]}


@router.get("/audit/verify")
def audit_verify(user: User = Depends(require("l1", "exec", "admin")), db: Session = Depends(get_db)):
    return audit.verify_chain(db)


@router.post("/audit/demo/tamper")
def tamper(user: User = Depends(require("admin")), db: Session = Depends(get_write_db, scope="function")):
    """DEMO ONLY: simulates an insider editing a row directly in the database (bypassing the app).
    Temporarily lifts the append-only trigger, changes one payment amount, and restores the trigger."""
    if not settings.demo_mode:
        raise HTTPException(403, "Disabled outside demo mode")
    if rulebook.get_setting(db, "tamper_backup", None):
        raise HTTPException(409, "A tampered row already exists. Restore it first.")
    row = db.execute(select(AuditLog).where(AuditLog.action == "payment.confirmed").order_by(AuditLog.id.desc())).scalar() \
        or db.execute(select(AuditLog).order_by(AuditLog.id.desc()).offset(3)).scalar()
    if row is None:
        raise HTTPException(409, "Not enough audit rows yet")
    original = row.payload
    data = json.loads(original)
    if "amount" in data:
        data["amount"] = round(float(data["amount"]) * 10, 2)
    else:
        data["tampered"] = True
    db.execute(text("DROP TRIGGER IF EXISTS audit_no_update"))
    db.execute(text("UPDATE audit_log SET payload = :p WHERE id = :i"), {"p": json.dumps(data, sort_keys=True), "i": row.id})
    db.execute(text(AUDIT_TRIGGERS[0]))
    rulebook.put_setting(db, "tamper_backup", {"id": row.id, "payload": original})
    return {"tampered_row": row.id, "action": row.action, "change": "amount × 10" if "amount" in data else "field added"}


@router.post("/audit/demo/restore")
def restore(user: User = Depends(require("admin")), db: Session = Depends(get_write_db, scope="function")):
    backup = rulebook.get_setting(db, "tamper_backup", None)
    if not backup:
        raise HTTPException(409, "Nothing to restore")
    db.execute(text("DROP TRIGGER IF EXISTS audit_no_update"))
    db.execute(text("UPDATE audit_log SET payload = :p WHERE id = :i"), {"p": backup["payload"], "i": backup["id"]})
    db.execute(text(AUDIT_TRIGGERS[0]))
    from ..models import Setting
    db.delete(db.get(Setting, "tamper_backup"))
    return {"restored_row": backup["id"]}


@router.get("/audit/demo/state")
def tamper_state(user: User = Depends(require("l1", "exec", "admin")), db: Session = Depends(get_db)):
    b = rulebook.get_setting(db, "tamper_backup", None)
    return {"tampered_row": b["id"] if b else None}


# ------------------------------------------------------------------ queues

@router.get("/promises")
def promises(status: str = "open", user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Promise, Case).join(Case, Case.id == Promise.case_id).where(
        scope_filter(db, user), Promise.status == status).order_by(Promise.promised_date.asc()).limit(300)).all()
    today = clock.local_today()
    return [{"id": p.id, "case_id": c.id, "account_no": c.account_no, "borrower": c.borrower.name_masked,
             "amount": p.amount, "promised_date": p.promised_date.isoformat(), "status": p.status, "channel": p.channel,
             "days_left": (p.promised_date - today).days, "agent": c.agent.name if c.agent else None,
             "case_status": c.status, "resolved_at": iso(p.resolved_at)} for p, c in rows]


@router.get("/escalations")
def escalations(user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_db)):
    rows = db.execute(select(Case).where(scope_filter(db, user), Case.status.in_(("ESCALATED", "BROKEN_PTP")))
                      .order_by(Case.priority.desc())).scalars().all()
    return [{"id": c.id, "account_no": c.account_no, "borrower": c.borrower.name_masked, "status": c.status,
             "broken_ptp_count": c.broken_ptp_count, "amount_due": c.amount_due, "risk_score": c.risk_score,
             "agent": c.agent.name if c.agent else None,
             "escalated_to": db.get(User, c.escalated_to_id).name if c.escalated_to_id else None} for c in rows]


@router.get("/disputes")
def disputes(status: str = "open", user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_db)):
    rows = db.execute(select(Dispute, Case).join(Case, Case.id == Dispute.case_id).where(
        scope_filter(db, user), Dispute.status == status).order_by(Dispute.created_at.desc())).all()
    return [{"id": d.id, "case_id": c.id, "account_no": c.account_no, "borrower": c.borrower.name_masked,
             "category": d.category, "description": d.description, "owner_queue": d.owner_queue, "status": d.status,
             "resolution": d.resolution, "raised_by": db.get(User, d.raised_by).name if d.raised_by else None,
             "created_at": iso(d.created_at), "resolved_at": iso(d.resolved_at), "amount_due": c.amount_due} for d, c in rows]


class ResolveIn(BaseModel):
    outcome: str  # resolved | rejected
    resolution: str = Field(min_length=4, max_length=1000)
    adjust_amount_due: float | None = None


@router.post("/disputes/{dispute_id}/resolve")
def resolve_dispute(dispute_id: str, body: ResolveIn, user: User = Depends(require(*MANAGERS)),
                    db: Session = Depends(get_write_db, scope="function")):
    d = db.get(Dispute, dispute_id)
    if not d or d.status != "open":
        raise HTTPException(409, "Dispute is not open")
    from .deps import get_case
    case = get_case(db, d.case_id, user)
    if body.outcome not in ("resolved", "rejected"):
        raise HTTPException(422, "outcome must be resolved or rejected")
    d.status, d.resolution, d.resolved_at = body.outcome, body.resolution, clock.utcnow()
    if body.adjust_amount_due is not None and body.outcome == "resolved":
        if body.adjust_amount_due < 0 or body.adjust_amount_due > case.amount_due:
            raise HTTPException(422, "Adjusted overdue must be between 0 and the current overdue")
        add_event(db, case, "adjustment", f"Overdue corrected ₹{case.amount_due:,.0f} → ₹{body.adjust_amount_due:,.0f}",
                  {"dispute_id": d.id}, user)
        case.amount_due = body.adjust_amount_due
    back = case.pre_payment_status if case.pre_payment_status in WORKING else (case.channel or "FIELD")
    if case.status == "DISPUTED":
        set_status(db, case, back if back in ("FIELD", "TELE", "DIGITAL") else "FIELD", user, "user",
                   f"Dispute {body.outcome}: {body.resolution}")
    add_event(db, case, "dispute", f"Dispute {body.outcome}", {"resolution": body.resolution}, user)
    audit.record(db, user, "dispute.closed", "dispute", d.id,
                 {"case": case.account_no, "outcome": body.outcome, "resolution": body.resolution})
    rescore(db, case, user, route=case.status in WORKING)
    touch(db, case, "dispute.closed")
    return {"ok": True, "case_status": case.status}


@router.get("/notifications")
def notifications(channel: str | None = None, status: str | None = None, limit: int = 100,
                  user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_db)):
    stmt = select(ContactAttempt, Case).join(Case, Case.id == ContactAttempt.case_id).where(
        scope_filter(db, user), ContactAttempt.channel != "call")
    if channel:
        stmt = stmt.where(ContactAttempt.channel == channel)
    if status:
        stmt = stmt.where(ContactAttempt.status == status)
    rows = db.execute(stmt.order_by(ContactAttempt.ts.desc()).limit(limit)).all()
    return [{"id": a.id, "case_id": c.id, "account_no": c.account_no, "borrower": c.borrower.name_masked,
             "channel": a.channel, "template": a.template, "language": a.language, "recipient": a.recipient,
             "body": a.body, "status": a.status, "block_reason": a.block_reason, "ts": iso(a.ts),
             "ts_local": local_str(a.ts)} for a, c in rows]


class ReviewIn(BaseModel):
    decision: str  # approve | reject
    note: str = Field(min_length=3, max_length=300)


@router.get("/visits/review")
def visits_for_review(user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_db)):
    rows = db.execute(select(Visit, Case, User).join(Case, Case.id == Visit.case_id).join(User, User.id == Visit.agent_id)
                      .where(scope_filter(db, user), Visit.review_status == "pending").order_by(Visit.server_ts.desc())
                      .limit(100)).all()
    return [{"id": v.id, "case_id": c.id, "account_no": c.account_no, "agent": u.name, "verification": v.verification,
             "distance_m": v.distance_m, "accuracy_m": v.accuracy_m, "outcome": v.outcome, "location_source": v.location_source,
             "ts": iso(v.server_ts)} for v, c, u in rows]


@router.post("/visits/{visit_id}/review")
def review_visit(visit_id: str, body: ReviewIn, user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_write_db, scope="function")):
    v = db.get(Visit, visit_id)
    if not v or v.review_status != "pending":
        raise HTTPException(409, "Visit is not awaiting review")
    from .deps import get_case
    case = get_case(db, v.case_id, user)
    v.review_status = "approved" if body.decision == "approve" else "rejected"
    add_event(db, case, "visit_review", f"Flagged visit {v.review_status} by manager", {"note": body.note, "visit_id": v.id}, user)
    audit.record(db, user, "visit.reviewed", "visit", v.id, {"decision": v.review_status, "note": body.note,
                                                           "verification": v.verification})
    return {"review_status": v.review_status}
