"""Case state machine. PAID and CLOSED can only be entered from the payment service
(gateway webhook or reconciliation). No API lets a user or the agent app set them."""
from __future__ import annotations

from fastapi import HTTPException

WORKING = {"NEW", "SCORED", "DIGITAL", "TELE", "FIELD"}

TRANSITIONS: dict[str, set[str]] = {
    "NEW": {"SCORED", "DIGITAL", "TELE", "FIELD"},
    "SCORED": {"DIGITAL", "TELE", "FIELD"},
    "DIGITAL": {"BROKEN_PTP", "TELE", "FIELD", "PTP", "PAYMENT_PENDING", "DISPUTED", "PAID", "CLOSED"},
    "TELE": {"BROKEN_PTP", "DIGITAL", "FIELD", "PTP", "PAYMENT_PENDING", "DISPUTED", "PAID", "CLOSED"},
    "FIELD": {"BROKEN_PTP", "DIGITAL", "TELE", "PTP", "PAYMENT_PENDING", "DISPUTED", "PAID", "CLOSED"},
    "PTP": {"PAYMENT_PENDING", "BROKEN_PTP", "DISPUTED", "PAID", "CLOSED", "FIELD", "TELE", "DIGITAL"},
    "PAYMENT_PENDING": {"PAID", "CLOSED", "FIELD", "TELE", "DIGITAL", "PTP", "ESCALATED", "BROKEN_PTP"},
    "BROKEN_PTP": {"ESCALATED", "FIELD", "PTP", "PAYMENT_PENDING", "PAID", "CLOSED", "DISPUTED"},
    "ESCALATED": {"FIELD", "TELE", "DIGITAL", "BROKEN_PTP", "PTP", "PAYMENT_PENDING", "PAID", "CLOSED", "DISPUTED"},
    "DISPUTED": {"FIELD", "TELE", "DIGITAL", "PAYMENT_PENDING", "PAID", "CLOSED"},
    "PAID": {"CLOSED", "FIELD", "TELE", "DIGITAL"},  # back to work only if a new delinquency arrives at intake
    "CLOSED": set(),
}

PAYMENT_ONLY = {"PAID", "CLOSED"}

LABELS = {
    "NEW": "New", "SCORED": "Scored", "DIGITAL": "Digital self-cure", "TELE": "Tele-calling",
    "FIELD": "Field visit", "PTP": "Promise to pay", "PAYMENT_PENDING": "Awaiting gateway",
    "PAID": "Paid (confirmed)", "CLOSED": "Closed", "BROKEN_PTP": "Promise broken",
    "ESCALATED": "Escalated", "DISPUTED": "Disputed",
}


def can(src: str, dst: str) -> bool:
    return dst in TRANSITIONS.get(src, set())


def assert_transition(src: str, dst: str, source: str) -> None:
    if dst in PAYMENT_ONLY and source not in ("gateway", "reconciliation", "intake"):
        raise HTTPException(409, f"{dst} can only be set by the payment gateway confirmation")
    if src == dst:
        return
    if not can(src, dst):
        raise HTTPException(409, f"Illegal status change {src} → {dst}")
