"""Runtime configuration. Every value can be overridden with an environment variable
(or a backend/.env file). Secrets that are not supplied are generated once and kept in
backend/data so restarts keep working tokens and readable encrypted PII."""
from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("RIQ_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "audio").mkdir(exist_ok=True)
STATIC_DIR = BASE_DIR / "static"


def _load_dotenv() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _persistent_secret(name: str, generator) -> str:
    value = os.getenv(name)
    if value:
        return value
    path = DATA_DIR / f".{name.lower()}"
    if path.exists():
        return path.read_text().strip()
    value = generator()
    path.write_text(value)
    return value


class Settings:
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'recoveriq.db').as_posix()}")
    jwt_secret: str = _persistent_secret("JWT_SECRET", lambda: secrets.token_urlsafe(48))
    pii_key: bytes = base64.b64decode(
        _persistent_secret("PII_ENC_KEY", lambda: base64.b64encode(secrets.token_bytes(32)).decode())
    )
    access_ttl_min: int = int(os.getenv("ACCESS_TTL_MIN", "15"))
    refresh_ttl_days: int = int(os.getenv("REFRESH_TTL_DAYS", "7"))
    timezone: str = os.getenv("TIMEZONE", "Asia/Kolkata")
    port: int = int(os.getenv("PORT", "8000"))

    # Payments: real Razorpay test mode when keys are present, otherwise the built-in sandbox gateway
    razorpay_key_id: str = os.getenv("RAZORPAY_KEY_ID", "")
    razorpay_key_secret: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    webhook_secret: str = _persistent_secret("RAZORPAY_WEBHOOK_SECRET", lambda: secrets.token_hex(24))

    # Optional LLM for translation + richer sentiment (rule-based fallback always works)
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "claude-haiku-5-5")

    demo_mode: bool = os.getenv("DEMO_MODE", "1") == "1"
    cors_origins: list[str] = [o for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o]

    @property
    def gateway(self) -> str:
        return "razorpay" if self.razorpay_key_id and self.razorpay_key_secret else "sandbox"


settings = Settings()
