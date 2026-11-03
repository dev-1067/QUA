"""Layer 1: rule scorecard. Fully explainable: every point added or removed is a reason."""
from __future__ import annotations

from datetime import timedelta

from .. import clock


def dpd_bucket(dpd: int) -> str:
    if dpd <= 0:
        return "CURRENT"
    if dpd <= 30:
        return "SMA-0"
    if dpd <= 60:
        return "SMA-1"
    if dpd <= 90:
        return "SMA-2"
    return "NPA"


def _inr(v: float) -> str:
    if v >= 100000:
        return f"₹{v / 100000:.1f}L"
    return f"₹{v:,.0f}"


def scorecard(case, rules: dict) -> tuple[int, list[dict]]:
    reasons: list[dict] = []

    def add(code: str, label: str, pts: int) -> None:
        if pts:
            reasons.append({"code": code, "label": label, "points": pts})

    dpd = case.dpd or 0
    for band in rules["dpd_points"]:
        if dpd >= band["min"] and (band["max"] is None or dpd <= band["max"]):
            add("DPD", f"{dpd} days past due", band["points"])
            break

    missed = min(case.missed_emis or 0, rules["missed_emi_cap"])
    add("MISSED_EMI", f"{case.missed_emis} missed EMI{'s' if case.missed_emis != 1 else ''}",
        missed * rules["missed_emi_points"])

    out_pts = 0
    for band in sorted(rules["outstanding_points"], key=lambda b: b["min"]):
        if (case.outstanding or 0) >= band["min"]:
            out_pts = band["points"]
    add("EXPOSURE", f"High exposure: {_inr(case.outstanding or 0)} outstanding", out_pts)

    broken = min(case.broken_ptp_count or 0, rules["broken_ptp_cap"])
    add("BROKEN_PTP", f"{case.broken_ptp_count} broken promise{'s' if case.broken_ptp_count != 1 else ''}",
        broken * rules["broken_ptp_points"])

    if (case.unreachable_streak or 0) >= rules["unreachable_streak"]:
        add("UNREACHABLE", f"Unreachable on last {case.unreachable_streak} attempts", rules["unreachable_points"])

    if case.last_reason_category == "willful_default":
        add("WILLFUL", "Latest note signals unwillingness to pay", rules["willful_points"])

    if case.last_collected_at and case.last_collected_at >= clock.utcnow() - timedelta(days=rules["recent_payment_days"]):
        add("RECENT_PAYMENT", f"Paid something in the last {rules['recent_payment_days']} days",
            rules["recent_payment_points"])

    if (case.kept_ptp_count or 0) > 0 and (case.broken_ptp_count or 0) == 0:
        add("KEPT_PTP", "Kept their last promise to pay", rules["kept_ptp_points"])

    score = max(0, min(100, sum(r["points"] for r in reasons)))
    reasons.sort(key=lambda r: -abs(r["points"]))
    return score, reasons


def priority(case, risk: int, rules: dict) -> float:
    amount_pct = min((case.amount_due or 0) / rules["amount_cap"], 1) * 100
    dpd_norm = min((case.dpd or 0) / rules["dpd_cap"], 1) * 100
    return round(rules["w_risk"] * risk + rules["w_amount"] * amount_pct + rules["w_dpd"] * dpd_norm, 2)


def decide_channel(case, risk: int, rules: dict) -> str:
    if risk >= rules["field_score"] or (case.outstanding or 0) >= rules["field_outstanding"]:
        return "FIELD"
    if risk >= rules["tele_score"]:
        return "TELE"
    return "DIGITAL"
