from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_write_db
from ..models import User
from ..security import ROLE_LABEL, current_user, decode_token, make_token, verify_password
from .deps import client_ip
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["auth"])
MAX_FAILS = 5
LOCK_MINUTES = 15


class LoginIn(BaseModel):
    email: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


def user_out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "role_label": ROLE_LABEL[u.role],
            "branch_id": u.branch_id, "branch": u.branch.name if u.branch else None, "region_id": u.region_id,
            "capacity": u.capacity, "home_lat": u.home_lat, "home_lng": u.home_lng}


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_write_db, scope="function")):
    user = db.execute(select(User).where(User.email == body.email.strip().lower())).scalar()
    now = datetime.utcnow()
    if user and user.locked_until and user.locked_until > now:
        mins = int((user.locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(423, f"Account locked after {MAX_FAILS} failed attempts. Try again in {mins} min.")
    if not user or not verify_password(body.password, user.password_hash):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= MAX_FAILS:
                user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                user.failed_logins = 0
            audit.record(db, user, "auth.login_failed", "user", user.id, {}, client_ip(request))
        # commit the counter, then report the failure
        db.commit()
        raise HTTPException(401, "Email or password is incorrect")
    user.failed_logins = 0
    user.locked_until = None
    audit.record(db, user, "auth.login", "user", user.id, {}, client_ip(request))
    return {"access_token": make_token(user), "refresh_token": make_token(user, "refresh"), "user": user_out(user)}


@router.post("/refresh")
def refresh(body: RefreshIn, db: Session = Depends(get_write_db, scope="function")):
    data = decode_token(body.refresh_token, "refresh")
    user = db.get(User, data["sub"])
    if not user or not user.active:
        raise HTTPException(401, "User disabled")
    return {"access_token": make_token(user), "refresh_token": make_token(user, "refresh"), "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)
