"""Payments: borrower pay page, sandbox gateway, signed webhook (the only way a case becomes PAID),
replay/forgery demos, reconciliation and receipts."""
from __future__ import annotations

import asyncio
import io
import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import actions, audit, clock
from ..config import settings
from ..db import get_db, get_write_db, write_session
from ..domain.state_machine import LABELS, WORKING, can
from ..integrations import gateway
from ..models import Case, Payment, PaymentLink, SandboxGatewayPayment, User, WebhookEvent
from ..realtime import hub
from ..security import MANAGERS, current_user, decrypt, mask_name, require
from ..services import add_event, apply_payment, set_status, touch
from .deps import client_ip, iso, scope_filter

log = logging.getLogger("recoveriq.payments")
router = APIRouter(tags=["payments"])
LENDER = "Sahyadri Finance Ltd (demo NBFC)"


def _link_by_token(db: Session, token: str) -> PaymentLink:
    link = db.execute(select(PaymentLink).where(PaymentLink.token == token)).scalar()
    if not link:
        raise HTTPException(404, "This payment link is not valid")
    return link


def _remaining(link: PaymentLink) -> float:
    return round(max(0.0, link.amount - (link.amount_paid or 0)), 2)


# ------------------------------------------------------------------ borrower pay page (public, signed token)

@router.get("/public/pay/{token}")
def pay_page(token: str, db: Session = Depends(get_db)):
    link = _link_by_token(db, token)
    case = db.get(Case, link.case_id)
    agent = case.agent
    payments = db.execute(select(Payment).where(Payment.link_id == link.id).order_by(Payment.confirmed_at.desc())).scalars()
    expired = link.expires_at < clock.utcnow()
    return {
        "lender": LENDER, "borrower": mask_name(decrypt(case.borrower.name_enc)),
        "account": "XXXX" + case.account_no[-4:], "loan_type": case.loan_type, "language": case.borrower.preferred_language,
        "amount": link.amount, "amount_paid": link.amount_paid, "remaining": _remaining(link), "status": link.status,
        "expired": expired, "case_status": case.status, "case_status_label": LABELS.get(case.status),
        "gateway": link.gateway, "amount_due_total": case.amount_due,
        "agent": {"name": agent.name, "id": "AG-" + agent.id[:6].upper(), "phone": agent.phone} if agent else None,
        "receipts": [{"id": p.id, "receipt_no": p.receipt_no, "amount": p.amount, "confirmed_at": iso(p.confirmed_at)}
                     for p in payments],
        "can_promise": case.status not in ("PAID", "CLOSED", "DISPUTED") and not expired,
    }


@router.post("/public/pay/{token}/checkout")
def checkout(token: str, db: Session = Depends(get_write_db, scope="function")):
    link = _link_by_token(db, token)
    case = db.get(Case, link.case_id)
    if link.expires_at < clock.utcnow():
        raise HTTPException(410, "This payment link has expired")
    if _remaining(link) <= 0 or case.status in ("PAID", "CLOSED"):
        raise HTTPException(409, "Nothing is due on this link")
    if link.status == "created":
        link.status = "initiated"
    if case.status != "PAYMENT_PENDING" and can(case.status, "PAYMENT_PENDING"):
        case.pre_payment_status = case.status
        set_status(db, case, "PAYMENT_PENDING", None, "borrower", "Borrower opened checkout", actor_label="borrower")
        touch(db, case, "payment.initiated")
    return {"gateway": link.gateway, "checkout_url": link.gateway_url if link.gateway == "razorpay"
            else f"/gateway/checkout/{link.gateway_link_id}"}


class BorrowerPromiseIn(BaseModel):
    amount: float
    promised_date: str


@router.post("/public/pay/{token}/promise")
def borrower_promise(token: str, body: BorrowerPromiseIn, db: Session = Depends(get_write_db, scope="function")):
    link = _link_by_token(db, token)
    case = db.get(Case, link.case_id)
    actor = case.agent or db.execute(select(User).where(User.role == "l2", User.branch_id == case.branch_id)).scalar()
    import uuid
    p, _ = actions.record_promise(db, case, actor, {"client_id": str(uuid.uuid4()), "amount": body.amount,
                                                    "promised_date": body.promised_date, "channel": "self-service"})
    add_event(db, case, "ptp", "Promise made by borrower on the pay page", {"promise_id": p.id}, actor_label="Borrower")
    return {"ok": True, "promised_date": p.promised_date.isoformat(), "amount": p.amount}


# ------------------------------------------------------------------ sandbox gateway (stands in for Razorpay's hosted page)

@router.get("/gateway/sandbox/{gateway_link_id}")
def sandbox_link(gateway_link_id: str, db: Session = Depends(get_db)):
    link = db.execute(select(PaymentLink).where(PaymentLink.gateway_link_id == gateway_link_id,
                                                PaymentLink.gateway == "sandbox")).scalar()
    if not link:
        raise HTTPException(404, "Unknown payment link")
    case = db.get(Case, link.case_id)
    return {"merchant": LENDER, "link_id": link.gateway_link_id, "amount": link.amount, "remaining": _remaining(link),
            "status": link.status, "token": link.token, "description": f"Loan repayment · XXXX{case.account_no[-4:]}"}


class SandboxPayIn(BaseModel):
    method: str = "upi"
    amount: float | None = None
    outcome: str = "success"     # success | failure
    delivery: str = "normal"     # normal | drop (simulate a lost webhook)


async def _deliver_and_mark(body: bytes, payment_id: str, delay: float) -> None:
    code, _ = await gateway.deliver(body, delay=delay)

    def mark():
        with write_session() as db:
            row = db.get(SandboxGatewayPayment, payment_id)
            if row and code == 200:
                row.webhook_delivered = True
    await asyncio.to_thread(mark)


@router.post("/gateway/sandbox/{gateway_link_id}/pay")
def sandbox_pay(gateway_link_id: str, body: SandboxPayIn, db: Session = Depends(get_write_db, scope="function")):
    link = db.execute(select(PaymentLink).where(PaymentLink.gateway_link_id == gateway_link_id,
                                                PaymentLink.gateway == "sandbox")).scalar()
    if not link:
        raise HTTPException(404, "Unknown payment link")
    remaining = _remaining(link)
    amount = round(body.amount if body.amount else remaining, 2)
    if amount < 1 or amount > remaining + 0.5:
        raise HTTPException(422, f"Amount must be between ₹1 and ₹{remaining:,.2f}")
    if body.method not in ("upi", "card", "netbanking", "wallet"):
        raise HTTPException(422, "Unsupported method")
    pay_id = gateway.new_id("pay")
    ok = body.outcome == "success"
    db.add(SandboxGatewayPayment(id=pay_id, link_id=gateway_link_id, amount=amount, method=body.method,
                                 status="captured" if ok else "failed", created_at=clock.utcnow()))
    case = db.get(Case, link.case_id)
    new_paid = (link.amount_paid or 0) + (amount if ok else 0)
    payload = gateway.build_webhook(
        ("payment_link.paid" if new_paid + 0.5 >= link.amount else "payment_link.partially_paid") if ok else "payment.failed",
        {"id": link.gateway_link_id, "amount": link.amount, "amount_paid": new_paid,
         "status": ("paid" if new_paid + 0.5 >= link.amount else "partially_paid") if ok else link.status,
         "reference_id": case.account_no},
        {"id": pay_id, "amount": amount, "status": "captured" if ok else "failed", "method": body.method,
         "error": None if ok else "Payment declined by bank (sandbox)"},
    )
    if body.delivery != "drop":
        asyncio.run_coroutine_threadsafe(_deliver_and_mark(payload, pay_id, 2.5), hub.loop)
    return {"payment_id": pay_id, "status": "captured" if ok else "failed", "amount": amount,
            "webhook": "scheduled in ~2.5 s" if body.delivery != "drop" else "dropped (use reconciliation)",
            "return_url": f"/p/{link.token}"}


# ------------------------------------------------------------------ webhook (the only path to PAID)

def process_webhook(db: Session, raw: bytes, signature: str | None, ip: str | None) -> tuple[int, dict]:
    ok_sig = gateway.verify(raw, signature)
    try:
        data = json.loads(raw)
    except ValueError:
        data = {}
    event = str(data.get("event", "unknown"))[:40]
    pay = (data.get("payload", {}).get("payment") or {}).get("entity") or {}
    link_e = (data.get("payload", {}).get("payment_link") or {}).get("entity") or {}
    log_row = WebhookEvent(gateway="razorpay" if settings.gateway == "razorpay" else "sandbox", event=event,
                           raw_body=raw.decode(errors="replace")[:20000], signature=signature, signature_ok=ok_sig,
                           result="pending", gateway_payment_id=pay.get("id"), received_at=clock.utcnow())
    db.add(log_row)

    def finish(code: int, result: str, **extra):
        log_row.result = result
        audit.record(db, None, "webhook.received", "webhook", log_row.id,
                     {"event": event, "result": result, "signature_ok": ok_sig, "payment_id": pay.get("id")}, ip,
                     actor_label="payment-gateway")
        return code, {"result": result, **extra}

    if not ok_sig:
        return finish(401, "rejected_bad_signature")
    link = db.execute(select(PaymentLink).where(PaymentLink.gateway_link_id == link_e.get("id"))).scalar()
    if link is None:
        return finish(200, "ignored_unknown_link")
    case = db.get(Case, link.case_id)
    if event == "payment.failed":
        if case.status == "PAYMENT_PENDING":
            back = case.pre_payment_status if case.pre_payment_status in WORKING | {"PTP", "ESCALATED"} else (case.channel or "FIELD")
            set_status(db, case, back, None, "gateway", "Payment failed at gateway", actor_label="payment-gateway")
        add_event(db, case, "payment_failed", "Payment attempt failed at gateway",
                  {"gateway_payment_id": pay.get("id"), "error": pay.get("error_description")}, actor_label="Payment gateway")
        touch(db, case, "payment.failed")
        return finish(200, "payment_failed_recorded")
    if event not in ("payment_link.paid", "payment_link.partially_paid", "payment.captured"):
        return finish(200, "ignored_event")
    if pay.get("status") != "captured" or not pay.get("id"):
        return finish(200, "ignored_not_captured")
    if db.execute(select(Payment.id).where(Payment.gateway_payment_id == pay["id"])).scalar():
        return finish(200, "duplicate_ignored")
    amount = round(int(pay["amount"]) / 100, 2)
    if amount > _remaining(link) + 0.5:
        return finish(422, "rejected_amount_exceeds_link")
    sp = db.begin_nested()
    try:
        p = apply_payment(db, link, pay["id"], amount, pay.get("method"), "webhook")
        sp.commit()
    except IntegrityError:
        sp.rollback()
        return finish(200, "duplicate_ignored")
    return finish(200, "posted", receipt_no=p.receipt_no, case_status=case.status)


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    raw = await request.body()
    sig = request.headers.get("x-razorpay-signature")
    ip = client_ip(request)

    def run():
        with write_session() as db:
            return process_webhook(db, raw, sig, ip)
    code, body = await asyncio.to_thread(run)
    return JSONResponse(body, status_code=code)


# ------------------------------------------------------------------ manager views & demo controls

@router.get("/payments")
def list_payments(limit: int = 100, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Payment, Case).join(Case, Case.id == Payment.case_id).where(scope_filter(db, user))
                      .order_by(Payment.confirmed_at.desc()).limit(limit)).all()
    return [{"id": p.id, "case_id": c.id, "account_no": c.account_no, "amount": p.amount, "receipt_no": p.receipt_no,
             "gateway": p.gateway, "gateway_payment_id": p.gateway_payment_id, "method": p.method, "source": p.source,
             "confirmed_at": iso(p.confirmed_at), "case_status": c.status} for p, c in rows]


@router.get("/payments/webhooks")
def webhook_log(limit: int = 60, user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_db)):
    rows = db.execute(select(WebhookEvent).order_by(WebhookEvent.received_at.desc()).limit(limit)).scalars()
    return [{"id": w.id, "event": w.event, "signature_ok": w.signature_ok, "result": w.result,
             "gateway_payment_id": w.gateway_payment_id, "received_at": iso(w.received_at)} for w in rows]


@router.post("/payments/webhooks/{event_id}/replay")
async def replay_webhook(event_id: str, user: User = Depends(require(*MANAGERS))):
    def load():
        with write_session() as db:
            w = db.get(WebhookEvent, event_id)
            if not w:
                raise HTTPException(404, "Webhook event not found")
            audit.record(db, db.get(User, user.id), "webhook.replay_requested", "webhook", w.id, {"event": w.event})
            return w.raw_body.encode(), w.signature
    raw, sig = await asyncio.to_thread(load)
    code, text = await gateway.deliver(raw, signature=sig)
    return {"status_code": code, "response": json.loads(text) if text.startswith("{") else text}


@router.post("/payments/webhooks/forge")
async def forge_webhook(user: User = Depends(require("admin", "l1", "l2", "exec"))):
    """Sends a fabricated 'paid' webhook with a wrong signature to prove it is rejected."""
    def pick():
        with write_session() as db:
            # prefer an open link; any link works, since the signature check runs before anything else
            link = db.execute(select(PaymentLink).where(PaymentLink.status.in_(("created", "initiated")))
                              .order_by(PaymentLink.created_at.desc())).scalar()                 or db.execute(select(PaymentLink).order_by(PaymentLink.created_at.desc())).scalar()
            if not link:
                raise HTTPException(404, "Create a payment link first")
            audit.record(db, db.get(User, user.id), "webhook.forgery_test", "payment_link", link.id, {})
            return link.gateway_link_id, link.amount, db.get(Case, link.case_id).account_no
    lid, amount, acc = await asyncio.to_thread(pick)
    raw = gateway.build_webhook("payment_link.paid", {"id": lid, "amount": amount, "amount_paid": amount, "status": "paid",
                                                      "reference_id": acc},
                                {"id": gateway.new_id("pay_forged"), "amount": amount, "status": "captured", "method": "upi"})
    code, text = await gateway.deliver(raw, signature="0" * 64)
    return {"status_code": code, "response": json.loads(text) if text.startswith("{") else text, "target": acc}


def reconcile(db: Session) -> dict:
    posted = 0
    checked = 0
    if settings.gateway == "sandbox":
        rows = db.execute(select(SandboxGatewayPayment).where(SandboxGatewayPayment.status == "captured")).scalars().all()
        for g in rows:
            checked += 1
            if db.execute(select(Payment.id).where(Payment.gateway_payment_id == g.id)).scalar():
                continue
            link = db.execute(select(PaymentLink).where(PaymentLink.gateway_link_id == g.link_id)).scalar()
            if link:
                apply_payment(db, link, g.id, g.amount, g.method, "reconciliation")
                posted += 1
    else:
        links = db.execute(select(PaymentLink).where(PaymentLink.status.in_(("created", "initiated", "partially_paid")),
                                                     PaymentLink.gateway == "razorpay")).scalars().all()
        for link in links:
            checked += 1
            try:
                for p in gateway.fetch_link_payments(link.gateway_link_id):
                    if not db.execute(select(Payment.id).where(Payment.gateway_payment_id == p["id"])).scalar():
                        apply_payment(db, link, p["id"], p["amount"], p.get("method"), "reconciliation")
                        posted += 1
            except Exception as exc:
                log.warning("Reconciliation failed for %s: %s", link.gateway_link_id, exc)
    if posted:
        audit.record(db, None, "reconciliation.posted", "payment", None, {"posted": posted}, actor_label="reconciliation-job")
    return {"checked": checked, "posted": posted}


@router.post("/payments/reconcile")
def run_reconcile(user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_write_db, scope="function")):
    return reconcile(db)


# ------------------------------------------------------------------ receipts

def receipt_pdf(db: Session, p: Payment) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    case = db.get(Case, p.case_id)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A5)
    w, h = A5
    ink, teal, muted = colors.HexColor("#14211d"), colors.HexColor("#0f766e"), colors.HexColor("#6b7280")
    c.setFillColor(ink)
    c.rect(0, h - 34 * mm, w, 34 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(14 * mm, h - 16 * mm, "Payment Receipt")
    c.setFont("Helvetica", 9)
    c.drawString(14 * mm, h - 23 * mm, LENDER)
    c.drawRightString(w - 14 * mm, h - 16 * mm, p.receipt_no)
    y = h - 48 * mm
    c.setFillColor(muted)
    c.setFont("Helvetica", 8)
    c.drawString(14 * mm, y, "AMOUNT RECEIVED")
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(14 * mm, y - 10 * mm, f"Rs. {p.amount:,.2f}")
    c.setFillColor(teal)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(14 * mm, y - 17 * mm, "Confirmed by payment gateway")
    rows = [
        ("Borrower", mask_name(decrypt(case.borrower.name_enc))),
        ("Loan account", "XXXX" + case.account_no[-4:]),
        ("Gateway payment ID", p.gateway_payment_id),
        ("Method", (p.method or "-").upper()),
        ("Confirmed at", clock.to_local(p.confirmed_at).strftime("%d %b %Y, %I:%M %p IST")),
        ("Confirmation source", "Signed webhook" if p.source == "webhook" else "Gateway reconciliation"),
        ("Remaining overdue", f"Rs. {case.amount_due:,.2f}"),
    ]
    y -= 30 * mm
    for k, v in rows:
        c.setFillColor(muted)
        c.setFont("Helvetica", 8)
        c.drawString(14 * mm, y, k)
        c.setFillColor(ink)
        c.setFont("Helvetica", 10)
        c.drawRightString(w - 14 * mm, y, str(v))
        c.setStrokeColor(colors.HexColor("#e5e7eb"))
        c.line(14 * mm, y - 3 * mm, w - 14 * mm, y - 3 * mm)
        y -= 9 * mm
    c.setFillColor(muted)
    c.setFont("Helvetica", 7)
    c.drawString(14 * mm, 14 * mm, "This is a system-generated receipt. Prototype for QUASAR 5.0, no real money moved.")
    c.showPage()
    c.save()
    return buf.getvalue()


@router.get("/payments/{payment_id}/receipt.pdf")
def receipt(payment_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Payment, payment_id)
    if not p:
        raise HTTPException(404, "Payment not found")
    from .deps import get_case
    get_case(db, p.case_id, user)
    return StreamingResponse(io.BytesIO(receipt_pdf(db, p)), media_type="application/pdf",
                             headers={"Content-Disposition": f'inline; filename="{p.receipt_no.replace("/", "-")}.pdf"'})


@router.get("/public/pay/{token}/receipt/{payment_id}.pdf")
def public_receipt(token: str, payment_id: str, db: Session = Depends(get_db)):
    link = _link_by_token(db, token)
    p = db.get(Payment, payment_id)
    if not p or p.case_id != link.case_id:
        raise HTTPException(404, "Receipt not found")
    return StreamingResponse(io.BytesIO(receipt_pdf(db, p)), media_type="application/pdf",
                             headers={"Content-Disposition": f'inline; filename="{p.receipt_no.replace("/", "-")}.pdf"'})
