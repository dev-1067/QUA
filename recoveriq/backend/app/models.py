from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uid() -> str:
    return str(uuid.uuid4())


class Region(Base):
    __tablename__ = "regions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(60), unique=True)


class Branch(Base):
    __tablename__ = "branches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    region_id: Mapped[str] = mapped_column(ForeignKey("regions.id"))
    name: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(60))
    state: Mapped[str] = mapped_column(String(60))
    pincode_prefix: Mapped[str] = mapped_column(String(6))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    region: Mapped[Region] = relationship()


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(120), unique=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(10))  # agent | l2 | l1 | exec | admin
    password_hash: Mapped[str] = mapped_column(String(200))
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"))
    region_id: Mapped[str | None] = mapped_column(ForeignKey("regions.id"))
    manager_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    capacity: Mapped[int] = mapped_column(Integer, default=25)
    home_lat: Mapped[float | None] = mapped_column(Float)
    home_lng: Mapped[float | None] = mapped_column(Float)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    branch: Mapped[Branch | None] = relationship()


class Borrower(Base):
    __tablename__ = "borrowers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name_enc: Mapped[str] = mapped_column(Text)
    phone_enc: Mapped[str] = mapped_column(Text)
    email_enc: Mapped[str | None] = mapped_column(Text)
    address_enc: Mapped[str] = mapped_column(Text)
    name_masked: Mapped[str] = mapped_column(String(80))
    phone_masked: Mapped[str] = mapped_column(String(20))
    pincode: Mapped[str] = mapped_column(String(6))
    city: Mapped[str] = mapped_column(String(60))
    state: Mapped[str] = mapped_column(String(60))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")
    opt_out: Mapped[list] = mapped_column(JSON, default=list)


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_queue", "status", "priority"),
        Index("ix_cases_bucket", "dpd_bucket"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    account_no: Mapped[str] = mapped_column(String(30), unique=True)
    borrower_id: Mapped[str] = mapped_column(ForeignKey("borrowers.id"))
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"))
    loan_type: Mapped[str] = mapped_column(String(30))
    principal: Mapped[float] = mapped_column(Float)
    emi_amount: Mapped[float] = mapped_column(Float)
    outstanding: Mapped[float] = mapped_column(Float)
    amount_due: Mapped[float] = mapped_column(Float)  # overdue amount to cure the account
    dpd: Mapped[int] = mapped_column(Integer)
    missed_emis: Mapped[int] = mapped_column(Integer)
    dpd_bucket: Mapped[str] = mapped_column(String(10))
    last_payment_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="NEW")
    pre_payment_status: Mapped[str | None] = mapped_column(String(20))
    channel: Mapped[str | None] = mapped_column(String(10))
    channel_rule_version: Mapped[int | None] = mapped_column(Integer)
    channel_override: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    scoring_rule_version: Mapped[int | None] = mapped_column(Integer)
    p_selfcure: Mapped[float | None] = mapped_column(Float)
    ml_reasons: Mapped[list] = mapped_column(JSON, default=list)
    model_version: Mapped[int | None] = mapped_column(Integer)
    priority: Mapped[float] = mapped_column(Float, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    default_rule_version: Mapped[int | None] = mapped_column(Integer)
    broken_ptp_count: Mapped[int] = mapped_column(Integer, default=0)
    kept_ptp_count: Mapped[int] = mapped_column(Integer, default=0)
    unreachable_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_sentiment: Mapped[str | None] = mapped_column(String(10))
    last_reason_category: Mapped[str | None] = mapped_column(String(30))
    collected_total: Mapped[float] = mapped_column(Float, default=0)
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime)
    assigned_agent_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    escalated_to_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    borrower: Mapped[Borrower] = relationship()
    branch: Mapped[Branch | None] = relationship()
    agent: Mapped[User | None] = relationship(foreign_keys=[assigned_agent_id])


class CaseEvent(Base):
    __tablename__ = "case_events"
    __table_args__ = (Index("ix_events_case", "case_id", "ts"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    actor_id: Mapped[str | None] = mapped_column(String(36))
    actor_name: Mapped[str | None] = mapped_column(String(80))
    ts: Mapped[datetime] = mapped_column(DateTime)


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(200))
    fit: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    assigned_by: Mapped[str | None] = mapped_column(String(36))
    assigned_at: Mapped[datetime] = mapped_column(DateTime)


class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = (Index("ix_visits_agent", "agent_id", "server_ts"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    client_id: Mapped[str] = mapped_column(String(36), unique=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float] = mapped_column(Float)
    distance_m: Mapped[float] = mapped_column(Float)
    verification: Mapped[str] = mapped_column(String(15))  # verified | flagged | low_conf | suspicious
    location_source: Mapped[str] = mapped_column(String(10), default="device")
    outcome: Mapped[str] = mapped_column(String(30))
    remarks: Mapped[str | None] = mapped_column(Text)
    device_ts: Mapped[datetime] = mapped_column(DateTime)
    server_ts: Mapped[datetime] = mapped_column(DateTime)
    review_status: Mapped[str | None] = mapped_column(String(15))


class ContactAttempt(Base):
    __tablename__ = "contact_attempts"
    __table_args__ = (Index("ix_contact_case", "case_id", "ts"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    client_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    channel: Mapped[str] = mapped_column(String(10))  # sms | whatsapp | email | call
    template: Mapped[str | None] = mapped_column(String(40))
    language: Mapped[str | None] = mapped_column(String(5))
    recipient: Mapped[str | None] = mapped_column(String(80))
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12))  # sent | delivered | blocked | failed | connected | no_answer
    block_reason: Mapped[str | None] = mapped_column(String(200))
    actor_id: Mapped[str | None] = mapped_column(String(36))
    ts: Mapped[datetime] = mapped_column(DateTime)


class Promise(Base):
    __tablename__ = "promises"
    __table_args__ = (Index("ix_ptp_due", "status", "promised_date"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    client_id: Mapped[str] = mapped_column(String(36), unique=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    amount: Mapped[float] = mapped_column(Float)
    promised_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | kept | broken
    channel: Mapped[str] = mapped_column(String(15), default="field")
    captured_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class PaymentLink(Base):
    __tablename__ = "payment_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    gateway: Mapped[str] = mapped_column(String(15))
    gateway_link_id: Mapped[str] = mapped_column(String(60), unique=True)
    token: Mapped[str] = mapped_column(String(80), unique=True)
    amount: Mapped[float] = mapped_column(Float)
    amount_paid: Mapped[float] = mapped_column(Float, default=0)
    gateway_url: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(15), default="created")  # created | initiated | paid | partially_paid | expired | cancelled
    created_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    link_id: Mapped[str | None] = mapped_column(ForeignKey("payment_links.id"))
    gateway: Mapped[str] = mapped_column(String(15))
    gateway_payment_id: Mapped[str] = mapped_column(String(60), unique=True)
    amount: Mapped[float] = mapped_column(Float)
    method: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(15), default="captured")
    receipt_no: Mapped[str] = mapped_column(String(30), unique=True)
    source: Mapped[str] = mapped_column(String(15), default="webhook")  # webhook | reconciliation
    collected_by: Mapped[str | None] = mapped_column(String(36))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    gateway: Mapped[str] = mapped_column(String(15))
    event: Mapped[str] = mapped_column(String(40))
    raw_body: Mapped[str] = mapped_column(Text)
    signature: Mapped[str | None] = mapped_column(String(200))
    signature_ok: Mapped[bool] = mapped_column(Boolean)
    result: Mapped[str] = mapped_column(String(40))
    gateway_payment_id: Mapped[str | None] = mapped_column(String(60))
    received_at: Mapped[datetime] = mapped_column(DateTime)


class SandboxGatewayPayment(Base):
    """The sandbox gateway's own ledger (what Razorpay would hold on its side).
    Reconciliation reads from here when a webhook never arrived."""
    __tablename__ = "sandbox_gateway_payments"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    link_id: Mapped[str] = mapped_column(String(60))
    amount: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(15))  # captured | failed
    webhook_delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    client_id: Mapped[str] = mapped_column(String(36), unique=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    language: Mapped[str] = mapped_column(String(5))
    source: Mapped[str] = mapped_column(String(10), default="typed")  # typed | voice
    original_text: Mapped[str] = mapped_column(Text)
    english_text: Mapped[str | None] = mapped_column(Text)
    audio_path: Mapped[str | None] = mapped_column(String(200))
    sentiment: Mapped[str] = mapped_column(String(10))
    sentiment_score: Mapped[float] = mapped_column(Float)
    reason_category: Mapped[str] = mapped_column(String(30))
    analyzer: Mapped[str] = mapped_column(String(20), default="lexicon")
    city: Mapped[str] = mapped_column(String(60))
    state: Mapped[str] = mapped_column(String(60))
    captured_at: Mapped[datetime] = mapped_column(DateTime)


class Dispute(Base):
    __tablename__ = "disputes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    client_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    category: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="open")  # open | resolved | rejected
    owner_queue: Mapped[str] = mapped_column(String(20))
    raised_by: Mapped[str | None] = mapped_column(String(36))
    resolution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class RuleVersion(Base):
    __tablename__ = "rule_versions"
    __table_args__ = (UniqueConstraint("kind", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(20))  # scoring | channel | default | contact_policy | priority
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(10))  # shadow | active | retired
    params: Mapped[dict] = mapped_column(JSON)  # coefficients, means, scales
    metrics: Mapped[dict] = mapped_column(JSON)
    training_rows: Mapped[int] = mapped_column(Integer)
    real_outcome_rows: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    approved_by: Mapped[str | None] = mapped_column(String(36))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime)
    actor_id: Mapped[str | None] = mapped_column(String(36))
    actor_name: Mapped[str | None] = mapped_column(String(80))
    role: Mapped[str | None] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(String(50))
    entity: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str | None] = mapped_column(String(60))
    payload: Mapped[str] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(50))
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class IntakeJob(Base):
    __tablename__ = "intake_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    filename: Mapped[str] = mapped_column(String(200))
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
