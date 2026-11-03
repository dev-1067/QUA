from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

_hasher = PasswordHasher()
_aes = AESGCM(settings.pii_key)

ROLE_RANK = {"agent": 1, "l2": 2, "l1": 3, "exec": 4, "admin": 5}
ROLE_LABEL = {"agent": "Field Agent", "l2": "Branch Manager (L2)", "l1": "Regional Manager (L1)",
              "exec": "Executive", "admin": "Administrator"}


# ---------- passwords ----------
def hash_password(pw: str) -> str:
    return _hasher.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, pw)
    except VerificationError:
        return False
    except Exception:
        return False


# ---------- tokens ----------
def make_token(user: User, kind: str = "access") -> str:
    ttl = timedelta(minutes=settings.access_ttl_min) if kind == "access" else timedelta(days=settings.refresh_ttl_days)
    now = datetime.utcnow()
    payload = {"sub": user.id, "role": user.role, "kind": kind, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str, kind: str = "access") -> dict:
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    if data.get("kind") != kind:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")
    return data


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    data = decode_token(auth[7:])
    user = db.get(User, data["sub"])
    if not user or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User disabled")
    return user


def require(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {', '.join(roles)}")
        return user
    return dep


MANAGERS = ("l2", "l1", "exec", "admin")


# ---------- PII ----------
def encrypt(value: str | None) -> str | None:
    if value is None:
        return None
    nonce = os.urandom(12)
    return base64.b64encode(nonce + _aes.encrypt(nonce, value.encode(), None)).decode()


def decrypt(value: str | None) -> str | None:
    if not value:
        return None
    raw = base64.b64decode(value)
    return _aes.decrypt(raw[:12], raw[12:], None).decode()


def mask_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())[-10:]
    if len(digits) < 6:
        return "XXXXXXXXXX"
    return digits[:2] + "X" * (len(digits) - 5) + digits[-3:]


def mask_name(name: str) -> str:
    parts = name.split()
    if not parts:
        return ""
    first = parts[0]
    rest = " ".join(p[0] + "." for p in parts[1:])
    return f"{first} {rest}".strip()
