"""Contact Policy Engine: compliance as code. Every outbound contact (SMS, WhatsApp, email,
agent call) passes through check() first. Blocked attempts are still logged with the reason."""
from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import clock
from ..models import ContactAttempt

COUNTED = ("sent", "delivered", "connected", "no_answer")


def _parse(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def check(db: Session, case, channel: str, rules: dict, now_utc: datetime | None = None) -> tuple[bool, str | None]:
    now_utc = now_utc or clock.utcnow()
    local = clock.to_local(now_utc)
    start, end = _parse(rules["window_start"]), _parse(rules["window_end"])
    if not (start <= local.time() < end):
        return False, (f"Quiet hours: contact allowed only {rules['window_start']}–{rules['window_end']} "
                       f"borrower local time (now {local:%H:%M}) · RBI fair-practice code")
    if case.status in ("PAID", "CLOSED"):
        return False, "Account is cured/closed: no further recovery contact"
    if case.status == "DISPUTED" and rules.get("pause_on_dispute", True):
        return False, "Contact paused while a dispute is open"
    opt_out = case.borrower.opt_out or []
    if channel in opt_out:
        return False, f"Borrower opted out of {channel.upper()}"
    cap = rules["caps"].get(channel)
    if cap:
        day_start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = (day_start_local - local.utcoffset()).replace(tzinfo=None)
        week_start = day_start - timedelta(days=local.weekday())

        def count(since: datetime) -> int:
            return db.execute(
                select(func.count()).select_from(ContactAttempt).where(
                    ContactAttempt.case_id == case.id, ContactAttempt.channel == channel,
                    ContactAttempt.status.in_(COUNTED), ContactAttempt.ts >= since, ContactAttempt.ts <= now_utc,
                )
            ).scalar() or 0

        if count(day_start) >= cap["day"]:
            return False, f"Frequency cap reached: max {cap['day']} {channel.upper()} per day"
        if count(week_start) >= cap["week"]:
            return False, f"Frequency cap reached: max {cap['week']} {channel.upper()} per week"
    return True, None
