"""Field actions. Shared by the online API and the offline sync endpoint, and idempotent on the
client-generated id, so replaying an outbox never creates duplicates."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit, clock
from .db import emit
from .domain import contact_policy, rules as rulebook, sentiment as senti
from .domain.geo import haversine_m, verify_visit
from .domain.state_machine import WORKING, can
from .integrations import llm
from .models import Case, ContactAttempt, Dispute, Note, Promise, User, Visit
from .services import add_event, rescore, set_status, touch

VISIT_OUTCOMES = {
    "met_borrower": "Met borrower", "promise_taken": "Promise taken", "payment_link_shared": "Payment link shared",
    "not_home": "Borrower not at home", "door_locked": "House locked", "shifted": "Borrower has shifted",
    "refused": "Refused to engage", "wrong_address": "Wrong address",
}
UNREACHABLE_VISIT = {"not_home", "door_locked", "shifted", "wrong_address"}
CALL_OUTCOMES = {"connected": "Connected", "no_answer": "No answer", "switched_off": "Switched off",
                 "wrong_number": "Wrong number", "callback_requested": "Callback requested"}
DISPUTE_QUEUES = {"wrong_amount": "operations", "already_paid": "operations", "fraud_claim": "legal",
                  "service_issue": "customer-service", "harassment_complaint": "compliance"}


def _parse_ts(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if not value:
        return clock.utcnow()
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    # device clocks run on real time; shift into the (possibly simulated) business clock
    dt = dt + timedelta(seconds=clock.get_offset())
    return min(dt, clock.utcnow())


def _client_id(value: str | None) -> str:
    try:
        return str(uuid.UUID(str(value))) if value else str(uuid.uuid4())
    except ValueError:
        raise HTTPException(422, "client_id must be a UUID")


def _require_assignee(case: Case, user: User) -> None:
    if user.role == "agent" and case.assigned_agent_id != user.id:
        raise HTTPException(403, "This case is not assigned to you")


# ------------------------------------------------------------------ visits

def record_visit(db: Session, case: Case, user: User, data: dict) -> tuple[Visit, bool]:
    cid = _client_id(data.get("client_id"))
    existing = db.execute(select(Visit).where(Visit.client_id == cid)).scalar()
    if existing:
        return existing, False
    _require_assignee(case, user)
    outcome = data.get("outcome", "met_borrower")
    if outcome not in VISIT_OUTCOMES:
        raise HTTPException(422, f"Unknown visit outcome '{outcome}'")
    lat, lng = float(data["lat"]), float(data["lng"])
    acc = float(data.get("accuracy_m") or 9999)
    device_ts = _parse_ts(data.get("device_ts"))
    server_ts = clock.utcnow()
    dist = haversine_m(lat, lng, case.borrower.lat, case.borrower.lng)
    prev = db.execute(select(Visit).where(Visit.agent_id == user.id).order_by(Visit.device_ts.desc()).limit(1)).scalar()
    prev_t = (prev.lat, prev.lng, prev.device_ts.timestamp()) if prev and prev.device_ts < device_ts else None
    verification, why = verify_visit(dist, acc, prev_t, lat, lng, device_ts.timestamp())
    v = Visit(client_id=cid, case_id=case.id, agent_id=user.id, lat=lat, lng=lng, accuracy_m=acc, distance_m=round(dist, 1),
              verification=verification, location_source=data.get("location_source", "device")[:10],
              outcome=outcome, remarks=(data.get("remarks") or "")[:1000] or None, device_ts=device_ts,
              server_ts=server_ts, review_status="pending" if verification != "verified" else None)
    db.add(v)
    db.flush()
    case.unreachable_streak = (case.unreachable_streak or 0) + 1 if outcome in UNREACHABLE_VISIT else 0
    offline = (server_ts - device_ts) > timedelta(minutes=2)
    add_event(db, case, "visit", f"Field visit: {VISIT_OUTCOMES[outcome]} · {verification.replace('_', ' ')}",
              {"visit_id": v.id, "verification": verification, "why": why, "distance_m": round(dist),
               "accuracy_m": acc, "synced_offline": offline, "remarks": v.remarks}, user)
    audit.record(db, user, "visit.checkin", "visit", v.id,
                 {"case": case.account_no, "lat": round(lat, 5), "lng": round(lng, 5), "verification": verification,
                  "device_ts": device_ts.isoformat(), "server_ts": server_ts.isoformat()})
    rescore(db, case, user, route=False)
    touch(db, case, "visit.checkin")
    emit(db, {"type": "field.checkin", "case_id": case.id, "account_no": case.account_no, "agent_id": user.id,
              "agent_name": user.name, "lat": lat, "lng": lng, "verification": verification, "outcome": outcome,
              "branch_id": case.branch_id, "region_id": case.branch.region_id if case.branch else None,
              "ts": server_ts.isoformat() + "Z"})
    return v, True


# ------------------------------------------------------------------ calls

def record_call(db: Session, case: Case, user: User, data: dict) -> tuple[ContactAttempt, bool]:
    cid = _client_id(data.get("client_id"))
    existing = db.execute(select(ContactAttempt).where(ContactAttempt.client_id == cid)).scalar()
    if existing:
        return existing, False
    _require_assignee(case, user)
    outcome = data.get("outcome", "connected")
    if outcome not in CALL_OUTCOMES:
        raise HTTPException(422, f"Unknown call outcome '{outcome}'")
    ts = _parse_ts(data.get("device_ts"))
    ok, reason = contact_policy.check(db, case, "call", rulebook.active(db, "contact_policy").definition, ts)
    status = (("connected" if outcome in ("connected", "callback_requested") else "no_answer") if ok else "blocked")
    ca = ContactAttempt(client_id=cid, case_id=case.id, channel="call", template=None, language=None,
                        recipient=case.borrower.phone_masked, body=(data.get("remarks") or None),
                        status=status, block_reason=reason, actor_id=user.id, ts=ts)
    db.add(ca)
    db.flush()
    if ok:
        case.unreachable_streak = 0 if status == "connected" else (case.unreachable_streak or 0) + 1
        add_event(db, case, "call", f"Call: {CALL_OUTCOMES[outcome]}", {"remarks": ca.body}, user)
        rescore(db, case, user, route=False)
    else:
        add_event(db, case, "policy_block", "Call blocked by Contact Policy", {"reason": reason}, user)
    audit.record(db, user, "contact.call" if ok else "contact.blocked", "case", case.id,
                 {"case": case.account_no, "outcome": outcome, "blocked_reason": reason})
    touch(db, case, "contact.call")
    return ca, True


# ------------------------------------------------------------------ promises

def record_promise(db: Session, case: Case, user: User, data: dict) -> tuple[Promise, bool]:
    cid = _client_id(data.get("client_id"))
    existing = db.execute(select(Promise).where(Promise.client_id == cid)).scalar()
    if existing:
        return existing, False
    _require_assignee(case, user)
    amount = float(data["amount"])
    pdate = date.fromisoformat(str(data["promised_date"])[:10])
    today = clock.local_today()
    if amount <= 0 or amount > (case.outstanding or 0) + 1:
        raise HTTPException(422, "Promised amount must be between ₹1 and the outstanding balance")
    if pdate < today or pdate > today + timedelta(days=45):
        raise HTTPException(422, "Promise date must be within the next 45 days")
    if case.status in ("PAID", "CLOSED"):
        raise HTTPException(409, "Case is already cured")
    for old in db.execute(select(Promise).where(Promise.case_id == case.id, Promise.status == "open")).scalars():
        old.status, old.resolved_at = "superseded", clock.utcnow()
    p = Promise(client_id=cid, case_id=case.id, amount=amount, promised_date=pdate, status="open",
                channel=data.get("channel", "field"), captured_by=user.id, created_at=clock.utcnow())
    db.add(p)
    db.flush()
    if can(case.status, "PTP"):
        set_status(db, case, "PTP", user, "user", f"Promise ₹{amount:,.0f} by {pdate:%d %b}")
    add_event(db, case, "ptp", f"Promise to pay ₹{amount:,.0f} by {pdate:%d %b %Y}", {"promise_id": p.id}, user)
    audit.record(db, user, "ptp.created", "promise", p.id,
                 {"case": case.account_no, "amount": amount, "date": pdate.isoformat()})
    touch(db, case, "ptp.created")
    return p, True


# ------------------------------------------------------------------ notes

def record_note(db: Session, case: Case, user: User, data: dict, audio_path: str | None = None) -> tuple[Note, bool]:
    cid = _client_id(data.get("client_id"))
    existing = db.execute(select(Note).where(Note.client_id == cid)).scalar()
    if existing:
        return existing, False
    _require_assignee(case, user)
    text = (data.get("text") or "").strip()
    if not text:
        raise HTTPException(422, "Note text is empty (voice transcript or typed text is required)")
    lang_hint = data.get("language")
    result = senti.analyse(text, lang_hint)
    llm_result = llm.analyse(text, result["language"]) if llm.available() else None
    if llm_result:
        result.update({k: llm_result[k] for k in ("sentiment", "reason_category", "english_text", "analyzer")})
        result["score"] = llm_result["score"]
    n = Note(client_id=cid, case_id=case.id, agent_id=user.id, language=result["language"],
             source="voice" if data.get("source") == "voice" else "typed", original_text=text[:4000],
             english_text=result.get("english_text"), audio_path=audio_path, sentiment=result["sentiment"],
             sentiment_score=result["score"], reason_category=result["reason_category"], analyzer=result["analyzer"],
             city=case.borrower.city, state=case.borrower.state, captured_at=_parse_ts(data.get("device_ts")))
    db.add(n)
    db.flush()
    case.last_sentiment, case.last_reason_category = n.sentiment, n.reason_category
    add_event(db, case, "note", f"{'Voice' if n.source == 'voice' else 'Typed'} note · {n.sentiment} · "
                                f"{senti.CATEGORIES.get(n.reason_category, n.reason_category)}",
              {"note_id": n.id, "language": n.language, "text": n.original_text[:280]}, user)
    audit.record(db, user, "note.created", "note", n.id,
                 {"case": case.account_no, "language": n.language, "sentiment": n.sentiment, "source": n.source})
    rescore(db, case, user, route=case.status in WORKING)
    touch(db, case, "note.created")
    emit(db, {"type": "sentiment.updated", "state": n.state, "city": n.city, "sentiment": n.sentiment,
              "branch_id": case.branch_id, "region_id": case.branch.region_id if case.branch else None})
    return n, True


# ------------------------------------------------------------------ disputes

def raise_dispute(db: Session, case: Case, user: User, data: dict) -> tuple[Dispute, bool]:
    cid = _client_id(data.get("client_id"))
    existing = db.execute(select(Dispute).where(Dispute.client_id == cid)).scalar()
    if existing:
        return existing, False
    _require_assignee(case, user)
    category = data.get("category")
    if category not in DISPUTE_QUEUES:
        raise HTTPException(422, f"Category must be one of {', '.join(DISPUTE_QUEUES)}")
    if db.execute(select(Dispute).where(Dispute.case_id == case.id, Dispute.status == "open")).scalar():
        raise HTTPException(409, "A dispute is already open for this case")
    d = Dispute(client_id=cid, case_id=case.id, category=category, description=(data.get("description") or "")[:2000],
                status="open", owner_queue=DISPUTE_QUEUES[category], raised_by=user.id, created_at=clock.utcnow())
    db.add(d)
    db.flush()
    if can(case.status, "DISPUTED"):
        case.pre_payment_status = case.status
        set_status(db, case, "DISPUTED", user, "user", f"Dispute: {category.replace('_', ' ')}")
    add_event(db, case, "dispute", f"Dispute raised: {category.replace('_', ' ')} → {d.owner_queue} queue",
              {"dispute_id": d.id, "description": d.description}, user)
    audit.record(db, user, "dispute.raised", "dispute", d.id, {"case": case.account_no, "category": category})
    touch(db, case, "dispute.raised")
    return d, True
