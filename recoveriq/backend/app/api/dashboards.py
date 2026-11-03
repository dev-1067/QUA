from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import case as sql_case, func, select
from sqlalchemy.orm import Session

from .. import clock
from ..db import get_db
from ..domain import rules as rulebook
from ..domain.sentiment import CATEGORIES
from ..models import Borrower, Case, ContactAttempt, Note, Payment, Promise, User, Visit
from ..security import MANAGERS, current_user, require
from .deps import iso, scope_filter

router = APIRouter(tags=["dashboards"])
BUCKETS = ["SMA-0", "SMA-1", "SMA-2", "NPA", "CURRENT"]


def _scoped_case_ids(db: Session, user: User):
    return select(Case.id).where(scope_filter(db, user))


@router.get("/dashboards/summary")
def summary(days: int = 30, user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_db)):
    sf = scope_filter(db, user)
    ids = _scoped_case_ids(db, user)
    since = clock.utcnow() - timedelta(days=days)
    open_f = Case.status.notin_(("PAID", "CLOSED"))

    totals = db.execute(select(
        func.count(), func.coalesce(func.sum(sql_case((open_f, Case.amount_due), else_=0)), 0),
        func.coalesce(func.sum(sql_case((open_f, 1), else_=0)), 0),
        func.coalesce(func.sum(sql_case((Case.is_default.is_(True), 1), else_=0)), 0),
    ).where(sf)).one()
    collected = db.execute(select(func.coalesce(func.sum(Payment.amount), 0), func.count())
                           .where(Payment.case_id.in_(ids), Payment.confirmed_at >= since)).one()
    by_status = dict(db.execute(select(Case.status, func.count()).where(sf).group_by(Case.status)).all())
    by_channel = dict(db.execute(select(Case.channel, func.count()).where(sf, open_f).group_by(Case.channel)).all())
    ageing = {b: {"count": 0, "amount": 0.0} for b in BUCKETS}
    for b, n, amt in db.execute(select(Case.dpd_bucket, func.count(), func.coalesce(func.sum(Case.amount_due), 0))
                                .where(sf, open_f).group_by(Case.dpd_bucket)).all():
        ageing.setdefault(b, {"count": 0, "amount": 0.0})
        ageing[b] = {"count": n, "amount": round(amt, 2)}

    # daily collections trend
    trend = defaultdict(float)
    for amt, ts in db.execute(select(Payment.amount, Payment.confirmed_at).where(Payment.case_id.in_(ids),
                                                                                 Payment.confirmed_at >= since)).all():
        trend[clock.to_local(ts).date().isoformat()] += amt
    today = clock.local_today()
    trend_list = [{"date": (today - timedelta(days=i)).isoformat(),
                   "amount": round(trend.get((today - timedelta(days=i)).isoformat(), 0), 2)} for i in range(min(days, 30) - 1, -1, -1)]

    # cost per recovery
    costs = rulebook.get_setting(db, "costs", rulebook.DEFAULT_COSTS)
    visits = db.execute(select(func.count()).select_from(Visit).where(Visit.case_id.in_(ids), Visit.server_ts >= since)).scalar()
    contacts = dict(db.execute(select(ContactAttempt.channel, func.count()).where(
        ContactAttempt.case_id.in_(ids), ContactAttempt.ts >= since,
        ContactAttempt.status.in_(("sent", "delivered", "connected", "no_answer"))).group_by(ContactAttempt.channel)).all())
    spend = visits * costs["visit"] + sum(contacts.get(ch, 0) * costs[ch] for ch in ("call", "sms", "whatsapp", "email"))
    recovered = float(collected[0] or 0)

    # digital self-cure: cases routed DIGITAL that got paid with zero field visits
    digital_paid = db.execute(select(func.count(func.distinct(Payment.case_id))).join(Case, Case.id == Payment.case_id)
                              .where(sf, Case.channel == "DIGITAL", Payment.confirmed_at >= since,
                                     ~Case.id.in_(select(Visit.case_id)))).scalar()
    digital_total = by_channel.get("DIGITAL", 0) + digital_paid

    ptp = dict(db.execute(select(Promise.status, func.count()).where(Promise.case_id.in_(ids), Promise.created_at >= since)
                          .group_by(Promise.status)).all())
    kept, broken = ptp.get("kept", 0), ptp.get("broken", 0)

    # agent performance
    agents_q = select(User).where(User.role == "agent")
    if user.role in ("l2", "l1"):
        from .deps import scope_branch_ids
        agents_q = agents_q.where(User.branch_id.in_(scope_branch_ids(db, user)))
    agents = db.execute(agents_q).scalars().all()
    a_ids = [a.id for a in agents]
    v_stats = {a: (n, ver) for a, n, ver in db.execute(
        select(Visit.agent_id, func.count(), func.sum(sql_case((Visit.verification == "verified", 1), else_=0)))
        .where(Visit.agent_id.in_(a_ids), Visit.server_ts >= since).group_by(Visit.agent_id)).all()}
    p_stats = dict(db.execute(select(Payment.collected_by, func.sum(Payment.amount)).where(
        Payment.collected_by.in_(a_ids), Payment.confirmed_at >= since).group_by(Payment.collected_by)).all())
    ptp_stats = defaultdict(lambda: {"open": 0, "kept": 0, "broken": 0})
    for a, st, n in db.execute(select(Promise.captured_by, Promise.status, func.count()).where(
            Promise.captured_by.in_(a_ids), Promise.created_at >= since).group_by(Promise.captured_by, Promise.status)).all():
        if st in ("open", "kept", "broken"):
            ptp_stats[a][st] = n
    loads = dict(db.execute(select(Case.assigned_agent_id, func.count()).where(
        Case.assigned_agent_id.in_(a_ids), open_f).group_by(Case.assigned_agent_id)).all())
    perf = []
    for a in agents:
        n, ver = v_stats.get(a.id, (0, 0))
        ps = ptp_stats[a.id]
        perf.append({"id": a.id, "name": a.name, "branch": a.branch.name if a.branch else None, "load": loads.get(a.id, 0),
                     "capacity": a.capacity, "visits": n, "verified_pct": round(ver / n, 3) if n else None,
                     "ptp_taken": ps["open"] + ps["kept"] + ps["broken"],
                     "ptp_kept_pct": round(ps["kept"] / (ps["kept"] + ps["broken"]), 3) if ps["kept"] + ps["broken"] else None,
                     "collected": round(p_stats.get(a.id, 0) or 0, 2)})
    perf.sort(key=lambda r: -r["collected"])

    return {
        "period_days": days,
        "kpis": {
            "total_cases": totals[0], "open_cases": int(totals[2]), "overdue_amount": round(totals[1], 2),
            "collected": round(recovered, 2), "payments": collected[1],
            "collection_rate": round(recovered / (recovered + totals[1]), 4) if recovered + totals[1] else 0,
            "cost_per_recovery": round(spend / recovered, 4) if recovered else None, "spend": round(spend, 2),
            "self_cure_rate": round(digital_paid / digital_total, 4) if digital_total else None,
            "ptp_kept_rate": round(kept / (kept + broken), 4) if kept + broken else None,
            "default_cases": int(totals[3]), "ptp_open": ptp.get("open", 0),
            "escalated": by_status.get("ESCALATED", 0), "disputed": by_status.get("DISPUTED", 0),
            "awaiting_gateway": by_status.get("PAYMENT_PENDING", 0),
        },
        "by_status": by_status, "by_channel": {k or "UNROUTED": v for k, v in by_channel.items()},
        "ageing": [{"bucket": b, **ageing[b]} for b in BUCKETS if b in ageing],
        "trend": trend_list, "agents": perf, "costs": costs,
        "contacts": contacts, "visits": visits,
    }


@router.get("/dashboards/field")
def field_activity(hours: int = 24, user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_db)):
    ids = _scoped_case_ids(db, user)
    since = clock.utcnow() - timedelta(hours=hours)
    rows = db.execute(select(Visit, User, Case).join(User, User.id == Visit.agent_id).join(Case, Case.id == Visit.case_id)
                      .where(Visit.case_id.in_(ids), Visit.server_ts >= since).order_by(Visit.server_ts.desc()).limit(400)).all()
    agents = db.execute(select(User).where(User.role == "agent", User.id.in_(
        select(Case.assigned_agent_id).where(scope_filter(db, user))))).scalars().all()
    return {
        "visits": [{"id": v.id, "lat": v.lat, "lng": v.lng, "verification": v.verification, "outcome": v.outcome,
                    "agent": u.name, "agent_id": u.id, "account_no": c.account_no, "case_id": c.id,
                    "distance_m": v.distance_m, "ts": iso(v.server_ts)} for v, u, c in rows],
        "agents": [{"id": a.id, "name": a.name, "lat": a.home_lat, "lng": a.home_lng} for a in agents],
    }


@router.get("/dashboards/sentiment")
def sentiment(level: str = "state", state: str | None = None, city: str | None = None,
              user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_db)):
    ids = _scoped_case_ids(db, user)
    base = select(Note).where(Note.case_id.in_(ids))
    if state:
        base = base.where(Note.state == state)
    if city:
        base = base.where(Note.city == city)
    notes = db.execute(base).scalars().all()
    groups: dict[str, dict] = {}
    key_of = {"state": lambda n: n.state, "city": lambda n: n.city, "borrower": lambda n: n.case_id}[level]
    for n in notes:
        g = groups.setdefault(key_of(n), {"key": key_of(n), "n": 0, "sum": 0.0, "pos": 0, "neg": 0, "neu": 0,
                                          "reasons": defaultdict(int), "state": n.state, "city": n.city})
        g["n"] += 1
        g["sum"] += n.sentiment_score
        g[{"positive": "pos", "negative": "neg"}.get(n.sentiment, "neu")] += 1
        g["reasons"][n.reason_category] += 1
    out = []
    names = {}
    if level == "borrower":
        for c in db.execute(select(Case).where(Case.id.in_(list(groups)))).scalars():
            names[c.id] = (c.account_no, c.borrower.name_masked)
    for k, g in groups.items():
        top = sorted(g["reasons"].items(), key=lambda kv: -kv[1])[:3]
        out.append({"key": k, "label": names.get(k, (None, k))[1] if level == "borrower" else k,
                    "account_no": names.get(k, (None,))[0] if level == "borrower" else None,
                    "state": g["state"], "city": g["city"], "notes": g["n"], "avg": round(g["sum"] / g["n"], 3),
                    "positive_pct": round(g["pos"] / g["n"], 3), "negative_pct": round(g["neg"] / g["n"], 3),
                    "top_reasons": [{"code": r, "label": CATEGORIES.get(r, r), "n": n} for r, n in top]})
    out.sort(key=lambda r: -r["notes"])
    reasons = defaultdict(int)
    for n in notes:
        reasons[n.reason_category] += 1
    recent = sorted(notes, key=lambda n: n.captured_at, reverse=True)[:12]
    return {"level": level, "items": out, "total_notes": len(notes),
            "reasons": [{"code": r, "label": CATEGORIES.get(r, r), "n": c} for r, c in sorted(reasons.items(), key=lambda kv: -kv[1])],
            "recent": [{"id": n.id, "case_id": n.case_id, "city": n.city, "state": n.state, "language": n.language,
                        "text": n.original_text[:200], "english_text": (n.english_text or "")[:200], "sentiment": n.sentiment,
                        "reason": CATEGORIES.get(n.reason_category), "ts": iso(n.captured_at)} for n in recent]}


@router.get("/leaderboard")
def leaderboard(days: int = 30, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Points = ₹ collected (gateway-confirmed) / 100 + 5 × verified visits + 10 × kept promises.
    Unverified visits and unconfirmed payments earn nothing, so rankings cannot be fabricated."""
    since = clock.utcnow() - timedelta(days=days)
    q = select(User).where(User.role == "agent")
    if user.role in ("agent", "l2"):
        q = q.where(User.branch_id == user.branch_id)
    elif user.role == "l1":
        from .deps import scope_branch_ids
        q = q.where(User.branch_id.in_(scope_branch_ids(db, user)))
    agents = db.execute(q).scalars().all()
    rows = []
    for a in agents:
        pays = db.execute(select(Payment, Case.account_no).join(Case, Case.id == Payment.case_id).where(
            Payment.collected_by == a.id, Payment.confirmed_at >= since)).all()
        visits = db.execute(select(Visit, Case.account_no).join(Case, Case.id == Visit.case_id).where(
            Visit.agent_id == a.id, Visit.server_ts >= since)).all()
        kept = db.execute(select(Promise, Case.account_no).join(Case, Case.id == Promise.case_id).where(
            Promise.captured_by == a.id, Promise.status == "kept", Promise.resolved_at >= since)).all()
        verified = [v for v, _ in visits if v.verification == "verified"]
        amount = sum(p.amount for p, _ in pays)
        points = round(amount / 100 + 5 * len(verified) + 10 * len(kept))
        rows.append({
            "id": a.id, "name": a.name, "branch": a.branch.name if a.branch else None, "points": points,
            "collected": round(amount, 2), "verified_visits": len(verified), "unverified_visits": len(visits) - len(verified),
            "kept_ptps": len(kept),
            "proof": {
                "payments": [{"account_no": acc, "amount": p.amount, "gateway_payment_id": p.gateway_payment_id,
                              "receipt_no": p.receipt_no, "ts": iso(p.confirmed_at)} for p, acc in pays[:25]],
                "visits": [{"account_no": acc, "verification": v.verification, "distance_m": v.distance_m,
                            "ts": iso(v.server_ts), "counts": v.verification == "verified"} for v, acc in visits[:25]],
                "kept_ptps": [{"account_no": acc, "amount": p.amount, "ts": iso(p.resolved_at)} for p, acc in kept[:25]],
            },
        })
    rows.sort(key=lambda r: -r["points"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return {"days": days, "formula": "₹ collected ÷ 100  +  5 × verified visits  +  10 × kept promises", "rows": rows}


@router.get("/compliance/report")
def compliance(days: int = 30, user: User = Depends(require("exec", "admin", "l1")), db: Session = Depends(get_db)):
    from ..models import AuditLog
    since = clock.utcnow() - timedelta(days=days)
    attempts = db.execute(select(ContactAttempt).where(ContactAttempt.ts >= since)).scalars().all()
    by_hour = [{"hour": h, "delivered": 0, "blocked": 0} for h in range(24)]
    blocked_reasons = defaultdict(int)
    outside = 0
    policy = rulebook.active(db, "contact_policy").definition
    start_h = int(policy["window_start"][:2])
    end_h = int(policy["window_end"][:2])
    for a in attempts:
        h = clock.to_local(a.ts).hour
        if a.status == "blocked":
            by_hour[h]["blocked"] += 1
            reason = (a.block_reason or "").split(":")[0]
            blocked_reasons[reason] += 1
        else:
            by_hour[h]["delivered"] += 1
            if not (start_h <= h < end_h):
                outside += 1
    reveals = db.execute(select(AuditLog).where(AuditLog.action == "pii.reveal", AuditLog.ts >= since)
                         .order_by(AuditLog.id.desc()).limit(50)).scalars().all()
    reassign = db.execute(select(AuditLog).where(AuditLog.action.in_(("case.reassign", "case.channel_override")),
                                                 AuditLog.ts >= since).order_by(AuditLog.id.desc()).limit(50)).scalars().all()
    import json
    return {
        "days": days, "window": f"{policy['window_start']}–{policy['window_end']}",
        "total_attempts": len(attempts), "delivered_outside_window": outside,
        "blocked_total": sum(blocked_reasons.values()),
        "blocked_reasons": [{"reason": k, "n": v} for k, v in sorted(blocked_reasons.items(), key=lambda kv: -kv[1])],
        "by_hour": by_hour,
        "pii_reveals": [{"ts": iso(r.ts), "actor": r.actor_name, "role": r.role, **json.loads(r.payload)} for r in reveals],
        "overrides": [{"ts": iso(r.ts), "actor": r.actor_name, "action": r.action, **json.loads(r.payload)} for r in reassign],
    }
