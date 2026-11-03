"""Tamper-evident audit log: hash = SHA256(prev_hash || canonical(row)). The table is
append-only (DB triggers), and verify_chain() reports the first row whose hash no longer matches."""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import clock
from .models import AuditLog, User

GENESIS = "0" * 64


def _canonical(ts, actor_id, role, action, entity, entity_id, payload: str) -> str:
    return json.dumps(
        [ts.isoformat(timespec="microseconds"), actor_id, role, action, entity, entity_id, payload],
        separators=(",", ":"), ensure_ascii=False,
    )


def compute_hash(prev_hash: str, row: AuditLog) -> str:
    body = _canonical(row.ts, row.actor_id, row.role, row.action, row.entity, row.entity_id, row.payload)
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()


def record(db: Session, actor: User | None, action: str, entity: str, entity_id: str | None,
           payload: dict | None = None, ip: str | None = None, actor_label: str | None = None,
           ts=None) -> AuditLog:
    """Must be called inside a write session (the global write lock keeps the chain ordered)."""
    db.flush()
    last = db.execute(select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1)).scalar()
    prev = last or GENESIS
    row = AuditLog(
        ts=ts or clock.utcnow(),
        actor_id=actor.id if actor else None,
        actor_name=actor.name if actor else (actor_label or "system"),
        role=actor.role if actor else "system",
        action=action,
        entity=entity,
        entity_id=entity_id,
        payload=json.dumps(payload or {}, sort_keys=True, default=str, ensure_ascii=False),
        ip=ip,
        prev_hash=prev,
    )
    row.hash = compute_hash(prev, row)
    db.add(row)
    db.flush()
    return row


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    count = 0
    for row in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars():
        count += 1
        if row.prev_hash != prev:
            return {"ok": False, "checked": count, "broken_at": row.id,
                    "reason": "prev_hash does not match the previous row's hash (row inserted or removed)"}
        expected = compute_hash(prev, row)
        if expected != row.hash:
            return {"ok": False, "checked": count, "broken_at": row.id,
                    "reason": "row contents changed after it was written",
                    "expected_hash": expected, "stored_hash": row.hash}
        prev = row.hash
    return {"ok": True, "checked": count, "head": prev}
