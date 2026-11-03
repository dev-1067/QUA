"""Case intake: CSV/XLSX upload with row-level validation. One case per account number:
re-uploading the same file creates nothing new (upsert)."""
from __future__ import annotations

import csv
import io
import math
import random
import re
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, clock
from ..db import get_db, write_session
from ..domain.geo import haversine_m
from ..domain.scoring import decide_channel
from ..domain import rules as rulebook
from ..domain.state_machine import WORKING
from ..models import Borrower, Branch, Case, IntakeJob, User
from ..security import current_user, encrypt, mask_name, mask_phone, require
from ..services import add_event, allocate, rescore, set_status, touch
from .deps import iso

router = APIRouter(prefix="/intake", tags=["intake"])

COLUMNS = ["account_no", "borrower_name", "phone", "email", "address", "pincode", "city", "state", "lat", "lng",
           "loan_type", "principal", "emi_amount", "outstanding", "dpd", "missed_emis", "last_payment_date",
           "preferred_language"]
REQUIRED = ["account_no", "borrower_name", "phone", "pincode", "emi_amount", "outstanding", "dpd"]
LOAN_TYPES = {"personal", "two_wheeler", "gold", "msme", "consumer_durable"}
LANGS = {"en", "hi", "mr"}


def _num(v, field, errors, integer=False, minimum=0):
    try:
        x = float(str(v).replace(",", "").replace("₹", "").strip())
        if math.isnan(x) or x < minimum:
            raise ValueError
        return int(x) if integer else round(x, 2)
    except (ValueError, TypeError):
        errors.append(f"{field} must be a number ≥ {minimum}")
        return None


def _phone(v, errors):
    digits = re.sub(r"\D", "", str(v or ""))
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) != 10 or digits[0] not in "6789":
        errors.append("phone must be a valid 10-digit Indian mobile number")
        return None
    return "+91" + digits


def _read_rows(filename: str, data: bytes) -> list[dict]:
    if filename.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        header = [str(h or "").strip().lower() for h in next(it)]
        return [{header[i]: ("" if v is None else v) for i, v in enumerate(row) if i < len(header)} for row in it
                if any(v not in (None, "") for v in row)]
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    reader.fieldnames = [(f or "").strip().lower() for f in reader.fieldnames or []]
    return [r for r in reader if any((v or "").strip() for v in r.values() if isinstance(v, str))]


def _branch_for(branches: list[Branch], pincode: str, city: str, lat, lng) -> Branch:
    for b in sorted(branches, key=lambda b: -len(b.pincode_prefix)):
        if pincode.startswith(b.pincode_prefix):
            return b
    for b in branches:
        if city and b.city.lower() == city.lower():
            return b
    if lat is not None and lng is not None:
        return min(branches, key=lambda b: haversine_m(lat, lng, b.lat, b.lng))
    return branches[0]


def process(db: Session, user: User, filename: str, rows: list[dict]) -> IntakeJob:
    branches = list(db.execute(select(Branch)).scalars())
    job = IntakeJob(filename=filename[:200], total_rows=len(rows), created=0, updated=0, unchanged=0, rejected=0,
                    errors=[], created_by=user.id, created_at=clock.utcnow())
    db.add(job)
    errors_out = []
    seen = set()
    touched_branches = set()
    ch_rule = rulebook.active(db, "channel").definition
    for idx, raw in enumerate(rows, start=2):
        r = {k: (str(v).strip() if v is not None else "") for k, v in raw.items()}
        errs = [f"missing {c}" for c in REQUIRED if not r.get(c)]
        if errs:
            job.rejected += 1
            errors_out.append({"row": idx, "account_no": r.get("account_no"), "errors": errs})
            continue
        acc = r["account_no"].upper()
        if acc in seen:
            job.rejected += 1
            errors_out.append({"row": idx, "account_no": acc, "errors": ["duplicate account_no within this file"]})
            continue
        seen.add(acc)
        phone = _phone(r["phone"], errs)
        pincode = re.sub(r"\D", "", r["pincode"])
        if len(pincode) != 6:
            errs.append("pincode must have 6 digits")
        emi = _num(r["emi_amount"], "emi_amount", errs, minimum=1)
        outstanding = _num(r["outstanding"], "outstanding", errs)
        dpd = _num(r["dpd"], "dpd", errs, integer=True)
        principal = _num(r.get("principal") or r["outstanding"], "principal", errs)
        missed = _num(r["missed_emis"], "missed_emis", errs, integer=True) if r.get("missed_emis") else (
            max(1, math.ceil((dpd or 0) / 30)) if dpd else 0)
        lat = _num(r["lat"], "lat", errs, minimum=-90) if r.get("lat") else None
        lng = _num(r["lng"], "lng", errs, minimum=-180) if r.get("lng") else None
        loan_type = (r.get("loan_type") or "personal").lower().replace("-", "_").replace(" ", "_")
        if loan_type not in LOAN_TYPES:
            errs.append(f"loan_type must be one of {', '.join(sorted(LOAN_TYPES))}")
        lang = (r.get("preferred_language") or "en").lower()[:2]
        lang = lang if lang in LANGS else "en"
        lpd = None
        if r.get("last_payment_date"):
            try:
                lpd = date.fromisoformat(r["last_payment_date"][:10])
            except ValueError:
                errs.append("last_payment_date must be YYYY-MM-DD")
        if errs:
            job.rejected += 1
            errors_out.append({"row": idx, "account_no": acc, "errors": errs})
            continue
        branch = _branch_for(branches, pincode, r.get("city", ""), lat, lng)
        if lat is None or lng is None:  # offline geocode: branch centroid + small jitter, flagged approximate
            rnd = random.Random(acc)
            lat, lng = branch.lat + rnd.uniform(-0.03, 0.03), branch.lng + rnd.uniform(-0.03, 0.03)
        amount_due = round(emi * missed, 2) if missed else 0.0

        case = db.execute(select(Case).where(Case.account_no == acc)).scalar()
        if case is None:
            b = Borrower(name_enc=encrypt(r["borrower_name"]), phone_enc=encrypt(phone), email_enc=encrypt(r.get("email") or None),
                         address_enc=encrypt(r.get("address") or f"{r.get('city', '')} {pincode}"),
                         name_masked=mask_name(r["borrower_name"]), phone_masked=mask_phone(phone), pincode=pincode,
                         city=r.get("city") or branch.city, state=r.get("state") or branch.state, lat=lat, lng=lng,
                         preferred_language=lang, opt_out=[])
            db.add(b)
            db.flush()
            case = Case(account_no=acc, borrower_id=b.id, branch_id=branch.id, loan_type=loan_type, principal=principal,
                        emi_amount=emi, outstanding=outstanding, amount_due=amount_due, dpd=dpd, missed_emis=missed,
                        dpd_bucket="", last_payment_date=lpd, status="NEW", created_at=clock.utcnow(),
                        updated_at=clock.utcnow())
            db.add(case)
            db.flush()
            add_event(db, case, "intake", f"Case created from {filename}", {"job_id": job.id, "row": idx}, user)
            rescore(db, case, user)
            job.created += 1
            touched_branches.add(branch.id)
            continue

        changes = {}
        for field, val in (("dpd", dpd), ("missed_emis", missed), ("outstanding", outstanding), ("emi_amount", emi),
                           ("amount_due", amount_due), ("loan_type", loan_type)):
            if getattr(case, field) != val:
                changes[field] = [getattr(case, field), val]
                setattr(case, field, val)
        if not changes:
            job.unchanged += 1
            continue
        job.updated += 1
        add_event(db, case, "intake", f"Updated from {filename}", {"job_id": job.id, "changes": changes}, user)
        if case.status == "PAID" and dpd and dpd > 0:
            ch = decide_channel(case, case.risk_score, ch_rule)
            set_status(db, case, ch, user, "intake", "New delinquency reported at intake")
        rescore(db, case, user, route=case.status in WORKING)
        touch(db, case)
        touched_branches.add(case.branch_id)
    job.errors = errors_out[:500]
    db.flush()
    alloc = allocate(db, list(touched_branches), user) if touched_branches else {"assigned": 0}
    audit.record(db, user, "intake.upload", "intake_job", job.id,
                 {"file": filename, "created": job.created, "updated": job.updated, "unchanged": job.unchanged,
                  "rejected": job.rejected, "auto_assigned": alloc["assigned"]})
    return job


def job_out(job: IntakeJob) -> dict:
    return {"id": job.id, "filename": job.filename, "total_rows": job.total_rows, "created": job.created,
            "updated": job.updated, "unchanged": job.unchanged, "rejected": job.rejected, "errors": job.errors,
            "created_at": iso(job.created_at)}


@router.post("/upload")
async def upload(file: UploadFile = File(...), user: User = Depends(require("admin", "l1", "l2"))):
    name = file.filename or "upload.csv"
    if not name.lower().endswith((".csv", ".xlsx", ".xlsm")):
        raise HTTPException(422, "Upload a .csv or .xlsx file")
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "File larger than 15 MB")
    try:
        rows = _read_rows(name, data)
    except Exception as exc:
        raise HTTPException(422, f"Could not read the file: {exc}")
    if not rows:
        raise HTTPException(422, "The file has no data rows")
    missing_cols = [c for c in REQUIRED if c not in rows[0]]
    if missing_cols:
        raise HTTPException(422, f"Missing required columns: {', '.join(missing_cols)}")
    import asyncio

    def run():
        with write_session() as db:
            job = process(db, db.get(User, user.id), name, rows)
            return job_out(job)
    return await asyncio.to_thread(run)


@router.get("/jobs")
def jobs(user: User = Depends(require("admin", "l1", "l2")), db: Session = Depends(get_db)):
    rows = db.execute(select(IntakeJob).order_by(IntakeJob.created_at.desc()).limit(30)).scalars()
    return [job_out(j) for j in rows]


@router.get("/sample.csv")
def sample(user: User = Depends(current_user)):
    rnd = random.Random(clock.local_today().toordinal())
    people = [("Sanjay Patil", "Dadar West, Mumbai", "400028", "Mumbai", "Maharashtra", 19.0178, 72.8478, "mr"),
              ("Kavita Iyer", "Andheri East, Mumbai", "400069", "Mumbai", "Maharashtra", 19.1136, 72.8697, "en"),
              ("Imran Shaikh", "Kurla West, Mumbai", "400070", "Mumbai", "Maharashtra", 19.0726, 72.8826, "hi"),
              ("Meena Deshmukh", "Kothrud, Pune", "411038", "Pune", "Maharashtra", 18.5074, 73.8077, "mr"),
              ("Rohit Verma", "Lajpat Nagar, New Delhi", "110024", "New Delhi", "Delhi", 28.5677, 77.2433, "hi"),
              ("Anita Joshi", "Naupada, Thane", "400602", "Thane", "Maharashtra", 19.1943, 72.9746, "mr")]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(COLUMNS)
    for i, (name, addr, pin, city, state, lat, lng, lang) in enumerate(people):
        emi = rnd.choice([2800, 4500, 6200, 9800, 15500])
        dpd = rnd.choice([12, 27, 44, 68, 95])
        missed = max(1, math.ceil(dpd / 30))
        outstanding = emi * rnd.randint(10, 30)
        w.writerow([f"SAMPLE{1000 + i}", name, f"9{rnd.randint(100000000, 999999999)}", f"{name.split()[0].lower()}@example.in",
                    f"{rnd.randint(1, 120)}, {addr}", pin, city, state, lat + rnd.uniform(-0.004, 0.004),
                    lng + rnd.uniform(-0.004, 0.004), rnd.choice(sorted(LOAN_TYPES)), outstanding * 1.2, emi, outstanding,
                    dpd, missed, "", lang])
    w.writerow(["SAMPLE9999", "Bad Row", "12345", "", "", "4000", "Mumbai", "Maharashtra", "", "", "personal",
                "", "abc", "50000", "30", "", "", "en"])
    return Response(out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="recoveriq_sample_intake.csv"'})
