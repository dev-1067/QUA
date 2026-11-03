"""Domain services shared by the API, the sync endpoint and background jobs."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from . import audit, clock
from .db import emit
from .domain import ml, rule_eval, rules as rulebook, scoring
from .domain.geo import haversine_m
from .domain.state_machine import LABELS, WORKING, assert_transition
from .models import Assignment, Case, CaseEvent, ModelVersion, Payment, PaymentLink, Promise, User

# ---------------------------------------------------------------- events

def case_event_payload(case: Case, kind: str, **extra) -> dict:
    return {
        "type": kind, "case_id": case.id, "account_no": case.account_no, "status": case.status,
        "branch_id": case.branch_id, "region_id": case.branch.region_id if case.branch else None,
        "agent_id": case.assigned_agent_id, "version": case.version, **extra,
    }


def add_event(db: Session, case: Case, type_: str, title: str, data: dict | None = None,
              actor: User | None = None, actor_label: str | None = None) -> CaseEvent:
    ev = CaseEvent(case_id=case.id, type=type_, title=title, data=data or {}, actor_id=actor.id if actor else None,
                   actor_name=actor.name if actor else (actor_label or "System"), ts=clock.utcnow())
    db.add(ev)
    return ev


def touch(db: Session, case: Case, kind: str = "case.updated", **extra) -> None:
    case.version = (case.version or 0) + 1
    case.updated_at = clock.utcnow()
    emit(db, case_event_payload(case, kind, **extra))


def set_status(db: Session, case: Case, dst: str, actor: User | None, source: str, reason: str | None = None,
               actor_label: str | None = None) -> None:
    src = case.status
    if src == dst:
        return
    assert_transition(src, dst, source)
    case.status = dst
    add_event(db, case, "status", f"{LABELS.get(src, src)} → {LABELS.get(dst, dst)}",
              {"from": src, "to": dst, "reason": reason, "source": source}, actor, actor_label)
    audit.record(db, actor, "case.status", "case", case.id,
                 {"account_no": case.account_no, "from": src, "to": dst, "reason": reason, "source": source},
                 actor_label=actor_label)


# ---------------------------------------------------------------- scoring

_model_cache: dict = {}


def active_model(db: Session) -> ModelVersion | None:
    if "active" in _model_cache:
        return _model_cache["active"]
    mv = db.execute(select(ModelVersion).where(ModelVersion.status == "active")).scalar()
    if mv is not None:
        db.expunge(mv)
    _model_cache["active"] = mv
    return mv


def clear_model_cache() -> None:
    _model_cache.clear()


def paid_recently(case: Case, days: int = 30) -> bool:
    return bool(case.last_collected_at and case.last_collected_at >= clock.utcnow() - timedelta(days=days))


def rescore(db: Session, case: Case, actor: User | None = None, route: bool = True, quiet: bool = False) -> dict:
    """Recompute risk, ML self-cure probability, default flag, priority and (optionally) channel."""
    sc_rule = rulebook.active(db, "scoring")
    ch_rule = rulebook.active(db, "channel")
    pr_rule = rulebook.active(db, "priority")
    df_rule = rulebook.active(db, "default")

    before = (case.risk_score, case.channel, case.is_default)
    case.dpd_bucket = scoring.dpd_bucket(case.dpd or 0)
    score, reasons = scoring.scorecard(case, sc_rule.definition)
    case.risk_score, case.reasons, case.scoring_rule_version = score, reasons, sc_rule.version

    mv = active_model(db)
    if mv is not None:
        p, ml_reasons = ml.predict(mv.params, ml.case_features(case, paid_recently(case)))
        case.p_selfcure, case.ml_reasons, case.model_version = p, ml_reasons, mv.version

    case.priority = scoring.priority(case, score, pr_rule.definition)
    try:
        tree = rule_eval.compile_rule(df_rule.definition["expression"])
        case.is_default = rule_eval.evaluate(tree, case) and case.status not in ("PAID", "CLOSED")
        case.default_rule_version = df_rule.version
    except rule_eval.RuleError:
        pass

    changed_channel = None
    if route and not case.channel_override and case.status in WORKING:
        new_channel = scoring.decide_channel(case, score, ch_rule.definition)
        if new_channel != case.channel or case.status != new_channel:
            changed_channel = (case.channel, new_channel)
            case.channel, case.channel_rule_version = new_channel, ch_rule.version
            if case.status != new_channel:
                src = case.status
                case.status = new_channel
                if not quiet:
                    add_event(db, case, "routing", f"Routed to {LABELS[new_channel]}",
                              {"from": src, "to": new_channel, "rule_version": ch_rule.version, "risk": score}, actor)
            if new_channel == "DIGITAL" and case.assigned_agent_id:
                unassign(db, case, actor, "Moved to digital self-cure")

    if not quiet and before[0] != score and before[0] is not None and before[0] != 0:
        add_event(db, case, "score", f"Risk score {before[0]} → {score}",
                  {"reasons": reasons[:3], "rule_version": sc_rule.version}, actor)
    if not quiet and before[2] is False and case.is_default:
        add_event(db, case, "default", "Classified as DEFAULT",
                  {"rule": df_rule.definition["expression"], "rule_version": df_rule.version}, actor)
    return {"score": score, "channel_changed": changed_channel}


# ---------------------------------------------------------------- allocation

ALLOC_RADIUS_KM = 15.0


def agent_loads(db: Session, agent_ids: list[str]) -> dict[str, int]:
    rows = db.execute(
        select(Case.assigned_agent_id, func.count()).where(
            Case.assigned_agent_id.in_(agent_ids), Case.status.notin_(("PAID", "CLOSED"))
        ).group_by(Case.assigned_agent_id)
    ).all()
    loads = {a: 0 for a in agent_ids}
    loads.update({a: n for a, n in rows})
    return loads


def bucket_performance(db: Session, agent_ids: list[str]) -> dict[tuple[str, str], float]:
    """Smoothed recovery rate per agent per DPD bucket: (paid + 1) / (assigned + 2)."""
    assigned = db.execute(
        select(Assignment.agent_id, Case.dpd_bucket, func.count(func.distinct(Case.id)))
        .join(Case, Case.id == Assignment.case_id)
        .where(Assignment.agent_id.in_(agent_ids)).group_by(Assignment.agent_id, Case.dpd_bucket)
    ).all()
    paid = db.execute(
        select(Payment.collected_by, Case.dpd_bucket, func.count(func.distinct(Payment.case_id)))
        .join(Case, Case.id == Payment.case_id)
        .where(Payment.collected_by.in_(agent_ids)).group_by(Payment.collected_by, Case.dpd_bucket)
    ).all()
    paid_map = {(a, b): n for a, b, n in paid}
    return {(a, b): (paid_map.get((a, b), 0) + 1) / (n + 2) for a, b, n in assigned}


def fit_score(agent: User, case: Case, load: int, perf: dict) -> tuple[float, dict]:
    dist_km = haversine_m(agent.home_lat or 0, agent.home_lng or 0, case.borrower.lat, case.borrower.lng) / 1000
    proximity = 1 - min(dist_km / ALLOC_RADIUS_KM, 1)
    bucket_perf = perf.get((agent.id, case.dpd_bucket), 0.5)
    headroom = max(0.0, 1 - load / max(agent.capacity, 1))
    fit = 0.45 * proximity + 0.30 * bucket_perf + 0.25 * headroom
    return round(fit, 4), {"distance_km": round(dist_km, 2), "proximity": round(proximity, 3),
                           "bucket_performance": round(bucket_perf, 3), "headroom": round(headroom, 3)}


def assign(db: Session, case: Case, agent: User, actor: User | None, reason: str, fit: float | None = None) -> None:
    for a in db.execute(select(Assignment).where(Assignment.case_id == case.id, Assignment.active.is_(True))).scalars():
        a.active = False
    prev = case.assigned_agent_id
    case.assigned_agent_id = agent.id
    db.add(Assignment(case_id=case.id, agent_id=agent.id, reason=reason, fit=fit,
                      assigned_by=actor.id if actor else None, assigned_at=clock.utcnow()))
    add_event(db, case, "assignment", f"Assigned to {agent.name}", {"reason": reason, "fit": fit, "previous": prev}, actor)
    touch(db, case, "case.assigned")
    if prev and prev != agent.id:
        emit(db, {"type": "case.unassigned", "case_id": case.id, "agent_id": prev, "branch_id": case.branch_id})


def unassign(db: Session, case: Case, actor: User | None, reason: str) -> None:
    prev = case.assigned_agent_id
    if not prev:
        return
    for a in db.execute(select(Assignment).where(Assignment.case_id == case.id, Assignment.active.is_(True))).scalars():
        a.active = False
    case.assigned_agent_id = None
    add_event(db, case, "assignment", "Unassigned", {"reason": reason, "previous": prev}, actor)
    emit(db, {"type": "case.unassigned", "case_id": case.id, "agent_id": prev, "branch_id": case.branch_id})


def branch_agents(db: Session, branch_ids: list[str]) -> list[User]:
    return list(db.execute(select(User).where(User.role == "agent", User.active.is_(True),
                                              User.branch_id.in_(branch_ids))).scalars())


def allocate(db: Session, branch_ids: list[str], actor: User | None) -> dict:
    agents = branch_agents(db, branch_ids)
    if not agents:
        return {"assigned": 0, "skipped_no_capacity": 0}
    loads = agent_loads(db, [a.id for a in agents])
    perf = bucket_performance(db, [a.id for a in agents])
    pending = list(db.execute(
        select(Case).where(Case.branch_id.in_(branch_ids), Case.assigned_agent_id.is_(None),
                           Case.channel.in_(("FIELD", "TELE")),
                           Case.status.notin_(("PAID", "CLOSED", "DISPUTED")))
        .order_by(Case.priority.desc())
    ).scalars())
    assigned, skipped = 0, 0
    for case in pending:
        best, best_fit, best_detail = None, -1.0, None
        for agent in agents:
            if agent.branch_id != case.branch_id or loads[agent.id] >= agent.capacity:
                continue
            fit, detail = fit_score(agent, case, loads[agent.id], perf)
            if fit > best_fit:
                best, best_fit, best_detail = agent, fit, detail
        if best is None:
            skipped += 1
            continue
        assign(db, case, best, actor,
               f"Auto-allocation · fit {best_fit:.2f} (distance {best_detail['distance_km']} km, "
               f"bucket recovery {best_detail['bucket_performance']:.0%}, headroom {best_detail['headroom']:.0%})",
               best_fit)
        loads[best.id] += 1
        assigned += 1
    return {"assigned": assigned, "skipped_no_capacity": skipped}


def rebalance(db: Session, branch_ids: list[str], actor: User | None) -> dict:
    moved = 0
    for branch_id in branch_ids:
        agents = branch_agents(db, [branch_id])
        if len(agents) < 2:
            continue
        loads = agent_loads(db, [a.id for a in agents])
        perf = bucket_performance(db, [a.id for a in agents])
        total = sum(loads.values())
        cap_total = sum(a.capacity for a in agents)
        for _ in range(500):
            util = {a.id: loads[a.id] / max(a.capacity, 1) for a in agents}
            hi = max(agents, key=lambda a: util[a.id])
            lo = min(agents, key=lambda a: util[a.id])
            target = total / cap_total if cap_total else 0
            if util[hi.id] - util[lo.id] <= 1.5 / max(lo.capacity, 1) or util[hi.id] <= target:
                break
            # move the lowest-priority case that is not mid-payment/promise
            case = db.execute(
                select(Case).where(Case.assigned_agent_id == hi.id,
                                   Case.status.in_(("FIELD", "TELE", "BROKEN_PTP", "ESCALATED")))
                .order_by(Case.priority.asc()).limit(1)
            ).scalar()
            if case is None:
                break
            fit, _ = fit_score(lo, case, loads[lo.id], perf)
            assign(db, case, lo, actor, f"Rebalance from {hi.name} ({loads[hi.id]}/{hi.capacity}) "
                                        f"to {lo.name} ({loads[lo.id]}/{lo.capacity})", fit)
            loads[hi.id] -= 1
            loads[lo.id] += 1
            moved += 1
    return {"moved": moved}


# ---------------------------------------------------------------- promises & payments

def receipt_number(db: Session) -> str:
    n = (db.execute(select(func.count()).select_from(Payment)).scalar() or 0) + 1
    return f"RIQ/{clock.local_today().year}/{n:06d}"


def apply_payment(db: Session, link: PaymentLink, gateway_payment_id: str, amount: float, method: str | None,
                  source: str) -> Payment:
    """The ONLY code path that records money and moves a case to PAID / CLOSED."""
    case = db.get(Case, link.case_id)
    pay = Payment(case_id=case.id, link_id=link.id, gateway=link.gateway, gateway_payment_id=gateway_payment_id,
                  amount=amount, method=method, status="captured", receipt_no=receipt_number(db), source=source,
                  collected_by=case.assigned_agent_id, confirmed_at=clock.utcnow())
    db.add(pay)
    db.flush()  # raises IntegrityError on a duplicate gateway_payment_id -> no double posting

    link.amount_paid = round((link.amount_paid or 0) + amount, 2)
    link.status = "paid" if link.amount_paid + 0.5 >= link.amount else "partially_paid"
    case.collected_total = round((case.collected_total or 0) + amount, 2)
    case.last_collected_at = clock.utcnow()
    case.amount_due = round(max(0.0, (case.amount_due or 0) - amount), 2)
    case.outstanding = round(max(0.0, (case.outstanding or 0) - amount), 2)
    label = "Gateway webhook" if source == "webhook" else "Reconciliation job"
    add_event(db, case, "payment", f"₹{amount:,.2f} confirmed by {label}",
              {"gateway_payment_id": gateway_payment_id, "receipt_no": pay.receipt_no, "method": method,
               "source": source}, actor_label="Payment gateway")
    audit.record(db, None, "payment.confirmed", "payment", pay.id,
                 {"case": case.account_no, "amount": amount, "gateway_payment_id": gateway_payment_id,
                  "receipt_no": pay.receipt_no, "source": source}, actor_label="payment-gateway")

    # promises satisfied by this money
    for ptp in db.execute(select(Promise).where(Promise.case_id == case.id, Promise.status == "open")).scalars():
        paid_since = db.execute(select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.case_id == case.id, Payment.confirmed_at >= ptp.created_at)).scalar()
        if paid_since + 0.5 >= ptp.amount:
            ptp.status, ptp.resolved_at = "kept", clock.utcnow()
            case.kept_ptp_count = (case.kept_ptp_count or 0) + 1
            add_event(db, case, "ptp", f"Promise of ₹{ptp.amount:,.0f} kept", {"promise_id": ptp.id})

    if case.outstanding <= 0.5:
        set_status(db, case, "CLOSED", None, "gateway", "Loan fully settled", actor_label="payment-gateway")
        case.dpd, case.missed_emis = 0, 0
    elif case.amount_due <= 0.5:
        if case.status != "PAID":
            set_status(db, case, "PAID", None, "gateway", "Overdue amount cleared", actor_label="payment-gateway")
        case.dpd, case.missed_emis = 0, 0
    else:
        # partial payment: account stays open with reduced dues
        back = case.pre_payment_status if case.pre_payment_status in WORKING | {"PTP", "ESCALATED"} else (case.channel or "FIELD")
        if case.status == "PAYMENT_PENDING":
            set_status(db, case, back, None, "gateway", "Part-payment received; dues remain",
                       actor_label="payment-gateway")
        if case.emi_amount:
            case.missed_emis = max(0, int(-(-case.amount_due // case.emi_amount)))
    rescore(db, case, route=case.status in WORKING)
    touch(db, case, "payment.confirmed", amount=amount, receipt_no=pay.receipt_no)
    return pay


def break_due_promises(db: Session) -> int:
    today = clock.local_today()
    grace = timedelta(days=1)
    due = [p for p in db.execute(select(Promise).where(Promise.status == "open",
                                                       Promise.promised_date < today - grace)).scalars()]
    for ptp in due:
        case = db.get(Case, ptp.case_id)
        ptp.status, ptp.resolved_at = "broken", clock.utcnow()
        case.broken_ptp_count = (case.broken_ptp_count or 0) + 1
        add_event(db, case, "ptp", f"Promise of ₹{ptp.amount:,.0f} for {ptp.promised_date:%d %b} broken",
                  {"promise_id": ptp.id}, actor_label="PTP scheduler")
        if case.status in ("PTP", "PAYMENT_PENDING", "FIELD", "TELE", "DIGITAL"):
            set_status(db, case, "BROKEN_PTP", None, "scheduler", "Due date + 1 day grace passed without payment",
                       actor_label="ptp-scheduler")
        rescore(db, case, route=False)
        if case.status == "BROKEN_PTP":
            if case.broken_ptp_count >= 2:
                manager = db.execute(select(User).where(User.role == "l2", User.branch_id == case.branch_id)).scalar()
                case.escalated_to_id = manager.id if manager else None
                set_status(db, case, "ESCALATED", None, "scheduler",
                           f"{case.broken_ptp_count} broken promises → escalated to {manager.name if manager else 'L2'}",
                           actor_label="ptp-scheduler")
            else:
                case.channel = "FIELD"
                set_status(db, case, "FIELD", None, "scheduler", "Next action: field visit after broken promise",
                           actor_label="ptp-scheduler")
                if not case.assigned_agent_id and case.branch_id:
                    allocate_one(db, case)
        touch(db, case, "ptp.broken")
    return len(due)


def allocate_one(db: Session, case: Case) -> None:
    agents = branch_agents(db, [case.branch_id])
    if not agents:
        return
    loads = agent_loads(db, [a.id for a in agents])
    perf = bucket_performance(db, [a.id for a in agents])
    scored = [(fit_score(a, case, loads[a.id], perf)[0], a) for a in agents if loads[a.id] < a.capacity]
    if scored:
        fit, agent = max(scored, key=lambda t: t[0])
        assign(db, case, agent, None, f"Auto-allocation after broken promise · fit {fit:.2f}", fit)


def open_case_filter():
    return and_(Case.status.notin_(("PAID", "CLOSED")))
