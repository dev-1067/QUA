from __future__ import annotations

import threading
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

is_sqlite = settings.database_url.startswith("sqlite")
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False, "timeout": 30} if is_sqlite else {},
    future=True,
)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        # let SQLAlchemy own transactions so SAVEPOINTs (per-op sync isolation) work with pysqlite
        dbapi_conn.isolation_level = None
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

    @event.listens_for(engine, "begin")
    def _sqlite_begin(conn):
        conn.exec_driver_sql("BEGIN")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# One writer at a time. Keeps the audit hash chain strictly ordered and makes every
# state transition (e.g. PAYMENT_PENDING -> PAID) atomic with its audit row.
# A plain Lock (not RLock): FastAPI may run a dependency's setup and teardown on different
# worker threads, and only an ownerless Lock can be released from another thread.
write_lock = threading.Lock()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_write_db():
    """Session for mutating endpoints: serialised, committed on success, rolled back on error.
    Realtime events queued during the request are published only after the commit."""
    from .realtime import hub

    with write_lock:
        db = SessionLocal()
        db.info["events"] = []
        try:
            yield db
            db.commit()
            events = db.info.get("events", [])
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    for evt in events:
        hub.publish_threadsafe(evt)


@contextmanager
def write_session():
    """Same guarantees as get_write_db for background jobs."""
    from .realtime import hub

    with write_lock:
        db = SessionLocal()
        db.info["events"] = []
        try:
            yield db
            db.commit()
            events = db.info.get("events", [])
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    for evt in events:
        hub.publish_threadsafe(evt)


def emit(db: Session, evt: dict) -> None:
    db.info.setdefault("events", []).append(evt)


AUDIT_TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log
       BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log
       BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END""",
]


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(engine)
    if is_sqlite:
        with engine.begin() as conn:
            for stmt in AUDIT_TRIGGERS:
                conn.execute(text(stmt))
