"""Versioned business rules. Every change creates a new version; cases remember which
version decided them, so any decision can be reproduced later."""
from __future__ import annotations

import copy

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import clock
from ..models import RuleVersion, Setting

DEFAULTS: dict[str, dict] = {
    "scoring": {
        "dpd_points": [
            {"min": 1, "max": 30, "points": 5},
            {"min": 31, "max": 60, "points": 15},
            {"min": 61, "max": 90, "points": 25},
            {"min": 91, "max": None, "points": 35},
        ],
        "missed_emi_points": 5, "missed_emi_cap": 4,
        "outstanding_points": [{"min": 100000, "points": 5}, {"min": 500000, "points": 10}],
        "broken_ptp_points": 5, "broken_ptp_cap": 3,
        "unreachable_points": 10, "unreachable_streak": 3,
        "willful_points": 10,
        "recent_payment_points": -10, "recent_payment_days": 30,
        "kept_ptp_points": -10,
    },
    "channel": {"field_score": 70, "field_outstanding": 100000, "tele_score": 40},
    "priority": {"w_risk": 0.6, "w_amount": 0.3, "w_dpd": 0.1, "amount_cap": 500000, "dpd_cap": 120},
    "default": {"expression": "missed_emis >= 3 or dpd > 90"},
    "contact_policy": {
        "window_start": "08:00", "window_end": "19:00",
        "caps": {
            "sms": {"day": 1, "week": 3},
            "whatsapp": {"day": 1, "week": 3},
            "email": {"day": 1, "week": 5},
            "call": {"day": 2, "week": 8},
        },
        "pause_on_dispute": True,
    },
}

DEFAULT_COSTS = {"visit": 150.0, "call": 4.0, "sms": 0.25, "whatsapp": 0.6, "email": 0.05}

_cache: dict[str, RuleVersion] = {}


def active(db: Session, kind: str) -> RuleVersion:
    cached = _cache.get(kind)
    if cached is not None:
        return cached
    row = db.execute(
        select(RuleVersion).where(RuleVersion.kind == kind, RuleVersion.active.is_(True))
        .order_by(RuleVersion.version.desc()).limit(1)
    ).scalar()
    if row is None:
        row = RuleVersion(kind=kind, version=1, definition=copy.deepcopy(DEFAULTS[kind]), active=True,
                          note="Initial rules", created_at=clock.utcnow())
        db.add(row)
        db.flush()
    db.expunge(row) if row in db else None
    _cache[kind] = row
    return row


def publish(db: Session, kind: str, definition: dict, actor_id: str | None, note: str | None) -> RuleVersion:
    current_max = db.execute(select(func.max(RuleVersion.version)).where(RuleVersion.kind == kind)).scalar() or 0
    for old in db.execute(select(RuleVersion).where(RuleVersion.kind == kind, RuleVersion.active.is_(True))).scalars():
        old.active = False
    row = RuleVersion(kind=kind, version=current_max + 1, definition=definition, active=True,
                      note=note, created_by=actor_id, created_at=clock.utcnow())
    db.add(row)
    db.flush()
    _cache.pop(kind, None)
    return row


def clear_cache() -> None:
    _cache.clear()


def get_setting(db: Session, key: str, default):
    row = db.get(Setting, key)
    return row.value if row else default


def put_setting(db: Session, key: str, value) -> None:
    row = db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
