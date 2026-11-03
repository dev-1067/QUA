"""Outbound message templates. Messages are delivered to the Notification Simulator inbox
(contact_attempts table) so every message is visible and auditable. Real SMS in India needs TRAI
DLT registration, so the prototype does not pretend to send carrier SMS."""
from __future__ import annotations

TEMPLATES = {
    "reminder": {
        "en": "Dear {name}, your {loan} EMI of ₹{amount} is overdue. Pay securely here: {link} – {lender}",
        "hi": "प्रिय {name}, आपकी {loan} की ₹{amount} की किस्त बकाया है। सुरक्षित भुगतान करें: {link} – {lender}",
        "mr": "प्रिय {name}, तुमच्या {loan} चा ₹{amount} चा हप्ता थकीत आहे. सुरक्षित भरणा येथे करा: {link} – {lender}",
    },
    "ptp_reminder": {
        "en": "Dear {name}, a gentle reminder of your promise to pay ₹{amount} by {date}. Pay here: {link} – {lender}",
        "hi": "प्रिय {name}, {date} तक ₹{amount} भुगतान के आपके वादे की याद दिला रहे हैं। यहाँ भुगतान करें: {link} – {lender}",
        "mr": "प्रिय {name}, {date} पर्यंत ₹{amount} भरण्याच्या तुमच्या वचनाची आठवण. येथे भरा: {link} – {lender}",
    },
    "settlement_offer": {
        "en": "Dear {name}, clear ₹{amount} today to bring your {loan} account back to regular. Pay: {link} – {lender}",
        "hi": "प्रिय {name}, आज ₹{amount} जमा कर अपना {loan} खाता नियमित करें। भुगतान: {link} – {lender}",
        "mr": "प्रिय {name}, आज ₹{amount} भरून तुमचे {loan} खाते नियमित करा. भरणा: {link} – {lender}",
    },
}

LOAN_NAMES = {
    "en": {"personal": "personal loan", "two_wheeler": "two-wheeler loan", "gold": "gold loan",
           "msme": "business loan", "consumer_durable": "consumer loan"},
    "hi": {"personal": "पर्सनल लोन", "two_wheeler": "दोपहिया लोन", "gold": "गोल्ड लोन",
           "msme": "बिज़नेस लोन", "consumer_durable": "कंज़्यूमर लोन"},
    "mr": {"personal": "वैयक्तिक कर्ज", "two_wheeler": "दुचाकी कर्ज", "gold": "सोने तारण कर्ज",
           "msme": "व्यवसाय कर्ज", "consumer_durable": "ग्राहक कर्ज"},
}

LENDER = "Sahyadri Finance (demo NBFC)"


def render(template: str, language: str, *, name: str, amount: float, link: str, loan_type: str,
           date: str = "") -> str:
    lang = language if language in ("en", "hi", "mr") else "en"
    tpl = TEMPLATES.get(template, TEMPLATES["reminder"])[lang]
    return tpl.format(name=name.split()[0], amount=f"{amount:,.0f}", link=link, date=date, lender=LENDER,
                      loan=LOAN_NAMES[lang].get(loan_type, LOAN_NAMES[lang]["personal"]))


# ---------------------------------------------------------------- real delivery (optional)
# Activated only by environment variables. Because demo borrowers are synthetic and their numbers
# could belong to real people, real messages go ONLY to the configured test recipient.
import os
import smtplib
from email.message import EmailMessage

import httpx


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def provider_for(channel: str) -> str | None:
    if channel in ("sms", "whatsapp") and _env("TWILIO_ACCOUNT_SID") and _env("TWILIO_AUTH_TOKEN") and _env("DEMO_RECIPIENT_PHONE"):
        if channel == "sms" and _env("TWILIO_SMS_FROM"):
            return "twilio"
        if channel == "whatsapp" and _env("TWILIO_WHATSAPP_FROM"):
            return "twilio"
    if channel == "email" and _env("SMTP_HOST") and _env("SMTP_FROM") and _env("DEMO_RECIPIENT_EMAIL"):
        return "smtp"
    return None


def send(channel: str, body: str, subject: str = "Your loan account") -> dict:
    """Returns {"provider", "recipient", "ok", "id"|"error"}; never raises."""
    provider = provider_for(channel)
    if provider is None:
        return {"provider": None, "ok": True}
    try:
        if provider == "twilio":
            to = _env("DEMO_RECIPIENT_PHONE")
            frm = _env("TWILIO_SMS_FROM") if channel == "sms" else _env("TWILIO_WHATSAPP_FROM")
            if channel == "whatsapp":
                to = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
                frm = frm if frm.startswith("whatsapp:") else f"whatsapp:{frm}"
            sid = _env("TWILIO_ACCOUNT_SID")
            r = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                           data={"To": to, "From": frm, "Body": body[:1500]}, auth=(sid, _env("TWILIO_AUTH_TOKEN")), timeout=12)
            if r.status_code >= 300:
                return {"provider": "twilio", "recipient": to, "ok": False,
                        "error": f"Twilio {r.status_code}: {r.json().get('message', r.text)[:160] if r.headers.get('content-type', '').startswith('application/json') else r.text[:160]}"}
            return {"provider": "twilio", "recipient": to, "ok": True, "id": r.json().get("sid")}
        to = _env("DEMO_RECIPIENT_EMAIL")
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = _env("SMTP_FROM"), to, subject
        msg.set_content(body)
        port = int(_env("SMTP_PORT") or 587)
        with smtplib.SMTP(_env("SMTP_HOST"), port, timeout=12) as smtp:
            if port != 25:
                smtp.starttls()
            if _env("SMTP_USER"):
                smtp.login(_env("SMTP_USER"), _env("SMTP_PASSWORD"))
            smtp.send_message(msg)
        return {"provider": "smtp", "recipient": to, "ok": True}
    except Exception as exc:  # provider down: the outbox still has the message
        return {"provider": provider, "ok": False, "error": str(exc)[:200]}
