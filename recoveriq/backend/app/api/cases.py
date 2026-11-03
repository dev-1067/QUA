from __future__ import annotations

import secrets
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import actions, audit, clock
from ..config import DATA_DIR
from ..db import get_db, get_write_db
from ..domain import contact_policy, rules as rulebook
from ..domain.sentiment import CATEGORIES
from ..domain.state_machine import LABELS, WORKING
from ..integrations import gateway, messaging
from ..models import (
    Assignment, Case, CaseEvent, ContactAttempt, Dispute, Note, Payment, PaymentLink, Promise, User, Visit,
)
from ..security import MANAGERS, current_user, decrypt, require
from ..services import add_event, assign, fit_score, agent_loads, bucket_performance, rescore, set_status, touch, unassign
from .deps import case_summary, client_ip, get_case, iso, scope_filter

router = APIRouter(prefix="/cases", tags=["cases"])

SORTS = {
    "priority": Case.priority.desc(), "risk": Case.risk_score.desc(), "dpd": Case.dpd.desc(),
    "amount": Case.amount_due.desc(), "updated": Case.updated_at.desc(), "selfcure": Case.p_selfcure.desc(),
}


@router.get("")
def list_cases(
    status: str | None = None, bucket: str | None = None, channel: str | None = None, agent_id: str | None = None,
    branch_id: str | None = None, q: str | None = None, default_only: bool = False, open_only: bool = False,
    sort: str = "priority", limit: int = Query(50, le=500), offset: int = 0,
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    stmt = select(Case).where(scope_filter(db, user))
    if status:
        stmt = stmt.where(Case.status.in_(status.split(",")))
    if bucket:
        stmt = stmt.where(Case.dpd_bucket == bucket)
    if channel:
        stmt = stmt.where(Case.channel == channel)
    if agent_id:
        stmt = stmt.where(Case.assigned_agent_id.is_(None) if agent_id == "none" else Case.assigned_agent_id == agent_id)
    if branch_id:
        stmt = stmt.where(Case.branch_id == branch_id)
    if default_only:
        stmt = stmt.where(Case.is_default.is_(True))
    if open_only:
        stmt = stmt.where(Case.status.notin_(("PAID", "CLOSED")))
    if q:
        from ..models import Borrower
        like = f"%{q.strip()}%"
        stmt = stmt.join(Borrower, Borrower.id == Case.borrower_id).where(or_(
            Case.account_no.ilike(like), Borrower.city.ilike(like), Borrower.pincode.ilike(like),
            Borrower.name_masked.ilike(like)))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar()
    rows = db.execute(stmt.order_by(SORTS.get(sort, SORTS["priority"])).limit(limit).offset(offset)).scalars().all()
    return {"total": total, "items": [case_summary(c, user) for c in rows]}


@router.get("/{case_id}")
def case_detail(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = get_case(db, case_id, user)
    b = case.borrower
    out = case_summary(case, user)
    agent_view = user.role == "agent"
    out.update({
        "principal": case.principal, "last_payment_date": case.last_payment_date.isoformat() if case.last_payment_date else None,
        "address": decrypt(b.address_enc) if agent_view else f"{b.city}, {b.state} {b.pincode[:3]}XXX",
        "phone_for_call": decrypt(b.phone_enc) if agent_view else None,
        "reasons": case.reasons, "ml_reasons": case.ml_reasons, "scoring_rule_version": case.scoring_rule_version,
        "channel_rule_version": case.channel_rule_version, "model_version": case.model_version,
        "default_rule_version": case.default_rule_version, "kept_ptp_count": case.kept_ptp_count,
        "unreachable_streak": case.unreachable_streak, "opt_out": b.opt_out or [],
        "pii_masked": not agent_view,
        "escalated_to": db.get(User, case.escalated_to_id).name if case.escalated_to_id else None,
    })
    q = lambda model, col, order: db.execute(select(model).where(col == case.id).order_by(order)).scalars().all()
    out["timeline"] = [{"id": e.id, "type": e.type, "title": e.title, "data": e.data, "actor": e.actor_name,
                        "ts": iso(e.ts)} for e in q(CaseEvent, CaseEvent.case_id, CaseEvent.ts.desc())[:150]]
    out["visits"] = [{"id": v.id, "lat": v.lat, "lng": v.lng, "accuracy_m": v.accuracy_m, "distance_m": v.distance_m,
                      "verification": v.verification, "outcome": v.outcome, "remarks": v.remarks,
                      "location_source": v.location_source, "device_ts": iso(v.device_ts), "server_ts": iso(v.server_ts),
                      "agent": db.get(User, v.agent_id).name} for v in q(Visit, Visit.case_id, Visit.server_ts.desc())]
    out["contacts"] = [{"id": c.id, "channel": c.channel, "status": c.status, "block_reason": c.block_reason,
                        "body": c.body, "template": c.template, "ts": iso(c.ts)}
                       for c in q(ContactAttempt, ContactAttempt.case_id, ContactAttempt.ts.desc())[:50]]
    out["promises"] = [{"id": p.id, "amount": p.amount, "promised_date": p.promised_date.isoformat(), "status": p.status,
                        "channel": p.channel, "created_at": iso(p.created_at)}
                       for p in q(Promise, Promise.case_id, Promise.created_at.desc())]
    out["payments"] = [{"id": p.id, "amount": p.amount, "receipt_no": p.receipt_no, "gateway_payment_id": p.gateway_payment_id,
                        "method": p.method, "source": p.source, "confirmed_at": iso(p.confirmed_at)}
                       for p in q(Payment, Payment.case_id, Payment.confirmed_at.desc())]
    out["links"] = [{"id": l.id, "amount": l.amount, "amount_paid": l.amount_paid, "status": l.status, "token": l.token,
                     "gateway": l.gateway, "gateway_link_id": l.gateway_link_id, "created_at": iso(l.created_at),
                     "expires_at": iso(l.expires_at)} for l in q(PaymentLink, PaymentLink.case_id, PaymentLink.created_at.desc())]
    out["notes"] = [{"id": n.id, "language": n.language, "source": n.source, "original_text": n.original_text,
                     "english_text": n.english_text, "sentiment": n.sentiment, "score": n.sentiment_score,
                     "reason_category": n.reason_category, "reason_label": CATEGORIES.get(n.reason_category),
                     "analyzer": n.analyzer, "has_audio": bool(n.audio_path), "captured_at": iso(n.captured_at)}
                    for n in q(Note, Note.case_id, Note.captured_at.desc())]
    out["disputes"] = [{"id": d.id, "category": d.category, "description": d.description, "status": d.status,
                        "owner_queue": d.owner_queue, "resolution": d.resolution, "created_at": iso(d.created_at)}
                       for d in q(Dispute, Dispute.case_id, Dispute.created_at.desc())]
    out["assignments"] = [{"agent": db.get(User, a.agent_id).name, "reason": a.reason, "active": a.active,
                           "assigned_at": iso(a.assigned_at)} for a in q(Assignment, Assignment.case_id, Assignment.assigned_at.desc())]
    policy = rulebook.active(db, "contact_policy").definition
    out["contact_policy"] = {ch: dict(zip(("allowed", "reason"), contact_policy.check(db, case, ch, policy)))
                             for ch in ("sms", "whatsapp", "email", "call")}
    if user.role in MANAGERS and case.branch_id:
        agents = db.execute(select(User).where(User.role == "agent", User.branch_id == case.branch_id)).scalars().all()
        loads = agent_loads(db, [a.id for a in agents])
        perf = bucket_performance(db, [a.id for a in agents])
        out["candidate_agents"] = sorted([
            {"id": a.id, "name": a.name, "load": loads[a.id], "capacity": a.capacity,
             **dict(zip(("fit", "detail"), fit_score(a, case, loads[a.id], perf)))} for a in agents
        ], key=lambda x: -x["fit"])
    return out


class RevealIn(BaseModel):
    reason: str = Field(min_length=8, max_length=300)


@router.post("/{case_id}/reveal-pii")
def reveal_pii(case_id: str, body: RevealIn, request: Request, user: User = Depends(require(*MANAGERS)),
               db: Session = Depends(get_write_db, scope="function")):
    case = get_case(db, case_id, user)
    b = case.borrower
    audit.record(db, user, "pii.reveal", "borrower", b.id, {"case": case.account_no, "reason": body.reason}, client_ip(request))
    add_event(db, case, "pii", "Borrower contact details revealed", {"reason": body.reason}, user)
    return {"name": decrypt(b.name_enc), "phone": decrypt(b.phone_enc), "email": decrypt(b.email_enc),
            "address": decrypt(b.address_enc)}


class ChannelIn(BaseModel):
    channel: str  # FIELD | TELE | DIGITAL | AUTO
    reason: str = Field(min_length=4, max_length=300)


@router.post("/{case_id}/channel")
def override_channel(case_id: str, body: ChannelIn, user: User = Depends(require(*MANAGERS)),
                     db: Session = Depends(get_write_db, scope="function")):
    case = get_case(db, case_id, user)
    if body.channel not in ("FIELD", "TELE", "DIGITAL", "AUTO"):
        raise HTTPException(422, "channel must be FIELD, TELE, DIGITAL or AUTO")
    prev = case.channel
    if body.channel == "AUTO":
        case.channel_override = False
        rescore(db, case, user)
    else:
        case.channel_override = True
        case.channel = body.channel
        if case.status in WORKING and case.status != body.channel:
            set_status(db, case, body.channel, user, "user", f"Manual channel override: {body.reason}")
        if body.channel == "DIGITAL":
            unassign(db, case, user, "Moved to digital self-cure")
    add_event(db, case, "routing", f"Channel {prev} → {case.channel} ({'auto' if body.channel == 'AUTO' else 'manual override'})",
              {"reason": body.reason}, user)
    audit.record(db, user, "case.channel_override", "case", case.id,
                 {"case": case.account_no, "from": prev, "to": case.channel, "reason": body.reason})
    touch(db, case)
    return case_summary(case, user)


class ReassignIn(BaseModel):
    agent_id: str
    reason: str = Field(min_length=4, max_length=300)


@router.post("/{case_id}/reassign")
def reassign(case_id: str, body: ReassignIn, user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_write_db, scope="function")):
    case = get_case(db, case_id, user)
    agent = db.get(User, body.agent_id)
    if not agent or agent.role != "agent" or agent.branch_id != case.branch_id:
        raise HTTPException(422, "Agent must belong to the case's branch")
    if case.status in ("PAID", "CLOSED"):
        raise HTTPException(409, "Case is already cured")
    if case.channel == "DIGITAL":
        case.channel, case.channel_override = "FIELD", True
        if case.status == "DIGITAL":
            set_status(db, case, "FIELD", user, "user", "Assigned to a field agent")
    assign(db, case, agent, user, f"Manual reassignment: {body.reason}")
    audit.record(db, user, "case.reassign", "case", case.id,
                 {"case": case.account_no, "agent": agent.name, "reason": body.reason})
    return case_summary(case, user)


class NudgeIn(BaseModel):
    channel: str  # sms | whatsapp | email
    template: str = "reminder"


def _active_link(db: Session, case: Case) -> PaymentLink | None:
    return db.execute(select(PaymentLink).where(
        PaymentLink.case_id == case.id, PaymentLink.status.in_(("created", "initiated", "partially_paid")),
        PaymentLink.expires_at > clock.utcnow()).order_by(PaymentLink.created_at.desc())).scalar()


def create_payment_link(db: Session, case: Case, user: User | None, amount: float) -> PaymentLink:
    if case.status in ("PAID", "CLOSED"):
        raise HTTPException(409, "Case is already cured")
    if amount < 1 or amount > (case.outstanding or 0) + 0.5:
        raise HTTPException(422, "Amount must be between ₹1 and the outstanding balance")
    try:
        g = gateway.create_link(amount, case.account_no, f"Repayment for {case.account_no}",
                                decrypt(case.borrower.name_enc), decrypt(case.borrower.phone_enc))
    except Exception as exc:
        raise HTTPException(502, f"Payment gateway error: {exc}")
    link = PaymentLink(case_id=case.id, gateway=g["gateway"], gateway_link_id=g["gateway_link_id"],
                       token=secrets.token_urlsafe(16), amount=round(amount, 2), gateway_url=g["gateway_url"],
                       status="created", created_by=user.id if user else None, created_at=clock.utcnow(),
                       expires_at=clock.utcnow() + timedelta(days=7))
    db.add(link)
    db.flush()
    add_event(db, case, "payment_link", f"Payment link created for ₹{amount:,.0f} ({g['gateway']})",
              {"link_id": link.id, "gateway_link_id": link.gateway_link_id}, user)
    audit.record(db, user, "payment_link.created", "payment_link", link.id,
                 {"case": case.account_no, "amount": amount, "gateway": g["gateway"]})
    touch(db, case, "payment_link.created")
    return link


def link_out(link: PaymentLink, request: Request) -> dict:
    base = str(request.base_url).rstrip("/")
    return {"id": link.id, "token": link.token, "amount": link.amount, "status": link.status, "gateway": link.gateway,
            "gateway_link_id": link.gateway_link_id, "pay_url": f"{base}/p/{link.token}", "path": f"/p/{link.token}",
            "expires_at": iso(link.expires_at)}


@router.post("/{case_id}/nudge")
def nudge(case_id: str, body: NudgeIn, request: Request, user: User = Depends(require(*MANAGERS)),
          db: Session = Depends(get_write_db, scope="function")):
    case = get_case(db, case_id, user)
    if body.channel not in ("sms", "whatsapp", "email"):
        raise HTTPException(422, "channel must be sms, whatsapp or email")
    policy = rulebook.active(db, "contact_policy").definition
    ok, reason = contact_policy.check(db, case, body.channel, policy)
    b = case.borrower
    now = clock.utcnow()
    if not ok:
        db.add(ContactAttempt(case_id=case.id, channel=body.channel, template=body.template, language=b.preferred_language,
                              recipient=b.phone_masked, body=None, status="blocked", block_reason=reason,
                              actor_id=user.id, ts=now))
        add_event(db, case, "policy_block", f"{body.channel.upper()} nudge blocked", {"reason": reason}, user)
        audit.record(db, user, "contact.blocked", "case", case.id,
                     {"case": case.account_no, "channel": body.channel, "reason": reason})
        touch(db, case, "contact.blocked")
        return {"sent": False, "reason": reason}
    link = _active_link(db, case) or create_payment_link(db, case, user, case.amount_due or case.emi_amount)
    url = link_out(link, request)["pay_url"]
    ptp = db.execute(select(Promise).where(Promise.case_id == case.id, Promise.status == "open")).scalar()
    text = messaging.render(body.template, b.preferred_language, name=decrypt(b.name_enc),
                            amount=ptp.amount if (ptp and body.template == "ptp_reminder") else link.amount - link.amount_paid,
                            link=url, loan_type=case.loan_type,
                            date=ptp.promised_date.strftime("%d %b") if ptp else "")
    recipient = (decrypt(b.email_enc) or "") if body.channel == "email" else b.phone_masked
    recipient = recipient if body.channel != "email" else recipient.split("@")[0][:2] + "***@" + recipient.split("@")[-1]
    real = messaging.send(body.channel, text)
    if real["provider"]:
        status = "sent" if real["ok"] else "failed"
        recipient = f"{recipient} · test copy via {real['provider']} → {real.get('recipient', '?')}"
    else:
        status = "delivered"
    db.add(ContactAttempt(case_id=case.id, channel=body.channel, template=body.template, language=b.preferred_language,
                          recipient=recipient[:80], body=text, status=status,
                          block_reason=None if real.get("ok", True) else real.get("error"), actor_id=user.id, ts=now))
    add_event(db, case, "nudge", f"{body.channel.upper()} nudge {status} ({b.preferred_language.upper()})"
              + (f" · real {real['provider']} send" if real["provider"] else ""), {"template": body.template, "text": text}, user)
    audit.record(db, user, "contact.nudge", "case", case.id,
                 {"case": case.account_no, "channel": body.channel, "template": body.template})
    touch(db, case, "contact.nudge")
    return {"sent": True, "text": text, "link": link_out(link, request), "provider": real["provider"],
            "provider_ok": real.get("ok", True), "provider_error": real.get("error")}


class LinkIn(BaseModel):
    amount: float | None = None


@router.post("/{case_id}/payment-link")
def payment_link(case_id: str, body: LinkIn, request: Request, user: User = Depends(current_user),
                 db: Session = Depends(get_write_db, scope="function")):
    case = get_case(db, case_id, user)
    if user.role not in ("agent",) + MANAGERS:
        raise HTTPException(403, "Not allowed")
    amount = body.amount or case.amount_due or case.emi_amount
    return link_out(create_payment_link(db, case, user, amount), request)


class ActionIn(BaseModel):
    model_config = {"extra": "allow"}


def _run(fn, case_id, body, user, db):
    case = get_case(db, case_id, user)
    obj, created = fn(db, case, user, body.model_dump())
    return {"id": obj.id, "created": created, "case": case_summary(case, user)}


@router.post("/{case_id}/visits")
def visit(case_id: str, body: ActionIn, user: User = Depends(current_user), db: Session = Depends(get_write_db, scope="function")):
    return _run(actions.record_visit, case_id, body, user, db)


@router.post("/{case_id}/calls")
def call(case_id: str, body: ActionIn, user: User = Depends(current_user), db: Session = Depends(get_write_db, scope="function")):
    case = get_case(db, case_id, user)
    obj, created = actions.record_call(db, case, user, body.model_dump())
    return {"id": obj.id, "created": created, "status": obj.status, "block_reason": obj.block_reason,
            "case": case_summary(case, user)}


@router.post("/{case_id}/promises")
def promise(case_id: str, body: ActionIn, user: User = Depends(current_user), db: Session = Depends(get_write_db, scope="function")):
    return _run(actions.record_promise, case_id, body, user, db)


@router.post("/{case_id}/disputes")
def dispute(case_id: str, body: ActionIn, user: User = Depends(current_user), db: Session = Depends(get_write_db, scope="function")):
    return _run(actions.raise_dispute, case_id, body, user, db)


@router.post("/{case_id}/notes")
def note(case_id: str, body: ActionIn, user: User = Depends(current_user), db: Session = Depends(get_write_db, scope="function")):
    case = get_case(db, case_id, user)
    n, created = actions.record_note(db, case, user, body.model_dump())
    return {"id": n.id, "created": created, "sentiment": n.sentiment, "score": n.sentiment_score,
            "reason_category": n.reason_category, "language": n.language, "english_text": n.english_text,
            "analyzer": n.analyzer, "case": case_summary(case, user)}


@router.post("/{case_id}/notes/audio")
async def note_audio(case_id: str, client_id: str = Form(...), text: str = Form(...), language: str = Form("hi"),
                     device_ts: str | None = Form(None), audio: UploadFile = File(...),
                     user: User = Depends(current_user)):
    data = await audio.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "Audio larger than 8 MB")
    from ..db import write_session
    with write_session() as db:
        case = get_case(db, case_id, user)
        user_db = db.get(User, user.id)
        ext = ".webm" if "webm" in (audio.content_type or "") else ".ogg" if "ogg" in (audio.content_type or "") else ".m4a"
        rel = f"audio/{client_id}{ext}"
        path = DATA_DIR / rel
        if not path.exists():
            path.write_bytes(data)
        n, created = actions.record_note(db, case, user_db, {"client_id": client_id, "text": text, "language": language,
                                                             "device_ts": device_ts, "source": "voice"}, rel)
        return {"id": n.id, "created": created, "sentiment": n.sentiment, "reason_category": n.reason_category,
                "language": n.language, "analyzer": n.analyzer}


@router.get("/{case_id}/notes/{note_id}/audio")
def note_audio_file(case_id: str, note_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    get_case(db, case_id, user)
    n = db.get(Note, note_id)
    if not n or n.case_id != case_id or not n.audio_path:
        raise HTTPException(404, "No audio")
    p = Path(DATA_DIR / n.audio_path)
    if not p.exists():
        raise HTTPException(404, "Audio file missing")
    return FileResponse(p, media_type="audio/webm")


@router.post("/{case_id}/rescore")
def rescore_case(case_id: str, user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_write_db, scope="function")):
    case = get_case(db, case_id, user)
    rescore(db, case, user)
    touch(db, case)
    return case_summary(case, user)
