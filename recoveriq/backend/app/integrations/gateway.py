"""Payment gateway adapter.

* razorpay mode (RAZORPAY_KEY_ID/SECRET set): real Razorpay Payment Links API in test mode.
* sandbox mode (default): a built-in gateway that behaves like Razorpay from our side. It keeps its
  own ledger, and confirms payments ONLY by sending an HMAC-SHA256 signed `payment_link.paid`
  webhook to our public webhook endpoint over HTTP, exactly the path a real gateway uses.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time

import httpx

from ..config import settings

log = logging.getLogger("recoveriq.gateway")
RZP_API = "https://api.razorpay.com/v1"


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(10).replace('-', 'x').replace('_', 'y')}"


def sign(body: bytes) -> str:
    return hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()


def verify(body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    return hmac.compare_digest(sign(body), signature)


# ------------------------------------------------------------------ link creation

def create_link(amount: float, account_no: str, description: str, customer_name: str, contact: str) -> dict:
    if settings.gateway == "razorpay":
        payload = {
            "amount": int(round(amount * 100)), "currency": "INR", "accept_partial": True,
            "first_min_partial_amount": 100, "reference_id": f"{account_no}-{int(time.time())}",
            "description": description[:255], "customer": {"name": customer_name, "contact": contact},
            "notify": {"sms": False, "email": False}, "reminder_enable": False,
        }
        r = httpx.post(f"{RZP_API}/payment_links", json=payload,
                       auth=(settings.razorpay_key_id, settings.razorpay_key_secret), timeout=20)
        r.raise_for_status()
        data = r.json()
        return {"gateway": "razorpay", "gateway_link_id": data["id"], "gateway_url": data["short_url"]}
    link_id = new_id("plink")
    return {"gateway": "sandbox", "gateway_link_id": link_id, "gateway_url": f"/gateway/checkout/{link_id}"}


def fetch_link_payments(gateway_link_id: str) -> list[dict]:
    """Razorpay reconciliation: payments the gateway holds for a link."""
    r = httpx.get(f"{RZP_API}/payment_links/{gateway_link_id}",
                  auth=(settings.razorpay_key_id, settings.razorpay_key_secret), timeout=20)
    r.raise_for_status()
    out = []
    for p in r.json().get("payments") or []:
        if p.get("status") == "captured":
            out.append({"id": p["payment_id"], "amount": p["amount"] / 100, "method": p.get("method")})
    return out


# ------------------------------------------------------------------ sandbox webhook

def build_webhook(event: str, link: dict, payment: dict) -> bytes:
    body = {
        "entity": "event", "account_id": "acc_RecoverIQSandbox", "event": event,
        "contains": ["payment_link", "payment"],
        "payload": {
            "payment_link": {"entity": {
                "id": link["id"], "amount": int(round(link["amount"] * 100)),
                "amount_paid": int(round(link.get("amount_paid", 0) * 100)), "status": link["status"],
                "reference_id": link["reference_id"], "currency": "INR"}},
            "payment": {"entity": {
                "id": payment["id"], "amount": int(round(payment["amount"] * 100)), "currency": "INR",
                "status": payment["status"], "method": payment["method"],
                "error_description": payment.get("error")}},
        },
        "created_at": int(time.time()),
    }
    return json.dumps(body, separators=(",", ":")).encode()


async def deliver(body: bytes, delay: float = 0.0, signature: str | None = None) -> tuple[int, str]:
    if delay:
        await asyncio.sleep(delay)
    url = f"http://127.0.0.1:{settings.port}/api/v1/webhooks/razorpay"
    headers = {"Content-Type": "application/json", "X-Razorpay-Signature": signature or sign(body),
               "X-Razorpay-Event-Id": new_id("evt")}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, content=body, headers=headers)
            return r.status_code, r.text
    except Exception as exc:
        log.error("Webhook delivery failed: %s", exc)
        return 0, str(exc)
