"""Agent app endpoints: prioritised worklist and offline sync (push outbox / pull changes)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import actions, clock
from ..db import get_db, get_write_db
from ..domain.geo import haversine_m
from ..models import Case, Payment, Promise, User, Visit
from ..security import current_user, decrypt, require
from .deps import case_summary, get_case, iso

router = APIRouter(tags=["agent"])


def worklist_item(db: Session, case: Case, user: User) -> dict:
    out = case_summary(case, user)
    b = case.borrower
    out["address"] = decrypt(b.address_enc)
    out["phone_for_call"] = decrypt(b.phone_enc)
    out["distance_km"] = round(haversine_m(user.home_lat or b.lat, user.home_lng or b.lng, b.lat, b.lng) / 1000, 1)
    out["reasons"] = case.reasons[:3]
    ptp = db.execute(select(Promise).where(Promise.case_id == case.id, Promise.status == "open")).scalar()
    out["ptp"] = {"amount": ptp.amount, "date": ptp.promised_date.isoformat()} if ptp else None
    return out


@router.get("/agent/worklist")
def worklist(user: User = Depends(require("agent")), db: Session = Depends(get_db)):
    cases = db.execute(select(Case).where(Case.assigned_agent_id == user.id, Case.status.notin_(("CLOSED",)))
                       .order_by(Case.priority.desc())).scalars().all()
    today_start = clock.local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    since = (today_start - today_start.utcoffset()).replace(tzinfo=None)
    visits_today = db.execute(select(func.count()).select_from(Visit).where(Visit.agent_id == user.id,
                                                                          Visit.server_ts >= since)).scalar()
    verified_today = db.execute(select(func.count()).select_from(Visit).where(
        Visit.agent_id == user.id, Visit.server_ts >= since, Visit.verification == "verified")).scalar()
    collected_today = db.execute(select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.collected_by == user.id, Payment.confirmed_at >= since)).scalar()
    items = [worklist_item(db, c, user) for c in cases]
    return {
        "server_time": iso(clock.utcnow()), "cursor": iso(clock.utcnow()),
        "stats": {"open": sum(1 for i in items if i["status"] not in ("PAID",)), "visits_today": visits_today,
                  "verified_today": verified_today, "collected_today": collected_today,
                  "ptp_due": sum(1 for i in items if i["ptp"] and i["ptp"]["date"] <= clock.local_today().isoformat())},
        "items": items,
    }


class SyncOp(BaseModel):
    client_id: str
    type: str  # visit | call | note | ptp | dispute
    case_id: str
    data: dict


class SyncPush(BaseModel):
    ops: list[SyncOp]


HANDLERS = {"visit": actions.record_visit, "call": actions.record_call, "note": actions.record_note,
            "ptp": actions.record_promise, "dispute": actions.raise_dispute}


@router.post("/sync/push")
def sync_push(body: SyncPush, user: User = Depends(require("agent")), db: Session = Depends(get_write_db, scope="function")):
    """Each op is applied in its own savepoint. Duplicates (same client_id) are acknowledged, not re-applied.
    Payment status can never be written from the device."""
    results = []
    for op in body.ops[:200]:
        handler = HANDLERS.get(op.type)
        if handler is None:
            results.append({"client_id": op.client_id, "status": "rejected", "error": f"Unsupported op '{op.type}'"})
            continue
        sp = db.begin_nested()
        try:
            case = get_case(db, op.case_id, user)
            obj, created = handler(db, case, user, {**op.data, "client_id": op.client_id})
            sp.commit()
            extra = {}
            if op.type == "call" and getattr(obj, "status", None) == "blocked":
                extra = {"warning": obj.block_reason}
            results.append({"client_id": op.client_id, "status": "applied" if created else "duplicate", **extra})
        except HTTPException as e:
            sp.rollback()
            results.append({"client_id": op.client_id, "status": "rejected", "error": e.detail})
        except Exception as e:  # malformed payloads must not poison the rest of the batch
            sp.rollback()
            results.append({"client_id": op.client_id, "status": "rejected", "error": str(e)[:200]})
    return {"results": results, "server_time": iso(clock.utcnow())}


@router.get("/sync/pull")
def sync_pull(since: str | None = None, user: User = Depends(require("agent")), db: Session = Depends(get_db)):
    stmt = select(Case).where(Case.assigned_agent_id == user.id)
    if since:
        ts = datetime.fromisoformat(since.replace("Z", "").split("+")[0])
        stmt = stmt.where(Case.updated_at > ts)
    cases = db.execute(stmt).scalars().all()
    return {"cursor": iso(clock.utcnow()), "items": [worklist_item(db, c, user) for c in cases]}


@router.get("/agent/visits")
def my_visits(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Visit).where(Visit.agent_id == user.id).order_by(Visit.server_ts.desc()).limit(50)).scalars()
    return [{"id": v.id, "case_id": v.case_id, "verification": v.verification, "outcome": v.outcome,
             "distance_m": v.distance_m, "server_ts": iso(v.server_ts)} for v in rows]
