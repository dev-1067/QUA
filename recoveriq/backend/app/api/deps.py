from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import select, true
from sqlalchemy.orm import Session

from .. import clock
from ..domain.state_machine import LABELS
from ..models import Branch, Case, User
from ..security import decrypt


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def scope_branch_ids(db: Session, user: User) -> list[str] | None:
    """None means unrestricted (exec/admin)."""
    if user.role in ("exec", "admin"):
        return None
    if user.role == "l1":
        return list(db.execute(select(Branch.id).where(Branch.region_id == user.region_id)).scalars())
    return [user.branch_id] if user.branch_id else []


def scope_filter(db: Session, user: User):
    if user.role == "agent":
        return Case.assigned_agent_id == user.id
    ids = scope_branch_ids(db, user)
    if ids is None:
        return true()
    return Case.branch_id.in_(ids)


def get_case(db: Session, case_id: str, user: User) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    if user.role == "agent" and case.assigned_agent_id != user.id:
        raise HTTPException(404, "Case not found")
    if user.role in ("l2", "l1"):
        ids = scope_branch_ids(db, user)
        if case.branch_id not in ids:
            raise HTTPException(404, "Case not found")
    return case


def iso(dt):
    return dt.isoformat() + "Z" if dt is not None and hasattr(dt, "hour") else (dt.isoformat() if dt else None)


def case_summary(case: Case, user: User) -> dict:
    b = case.borrower
    full = user.role == "agent"
    return {
        "id": case.id, "account_no": case.account_no,
        "borrower_name": decrypt(b.name_enc) if full else b.name_masked,
        "phone": b.phone_masked, "city": b.city, "state": b.state, "pincode": b.pincode,
        "lat": b.lat, "lng": b.lng, "language": b.preferred_language,
        "loan_type": case.loan_type, "outstanding": case.outstanding, "amount_due": case.amount_due,
        "emi_amount": case.emi_amount, "dpd": case.dpd, "missed_emis": case.missed_emis,
        "dpd_bucket": case.dpd_bucket, "status": case.status, "status_label": LABELS.get(case.status, case.status),
        "channel": case.channel, "channel_override": case.channel_override, "risk_score": case.risk_score,
        "p_selfcure": case.p_selfcure, "priority": case.priority, "is_default": case.is_default,
        "broken_ptp_count": case.broken_ptp_count, "top_reason": case.reasons[0]["label"] if case.reasons else None,
        "agent_id": case.assigned_agent_id, "agent_name": case.agent.name if case.agent else None,
        "branch": case.branch.name if case.branch else None, "branch_id": case.branch_id,
        "collected_total": case.collected_total, "last_sentiment": case.last_sentiment,
        "version": case.version, "updated_at": iso(case.updated_at),
    }


def local_str(dt) -> str | None:
    return clock.to_local(dt).strftime("%d %b %Y, %H:%M") if dt else None
