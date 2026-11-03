from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db, get_write_db
from ..models import Branch, Case, User
from ..security import MANAGERS, require
from ..services import agent_loads, allocate, rebalance
from .deps import scope_branch_ids

router = APIRouter(prefix="/allocation", tags=["allocation"])


def _branches(db: Session, user: User, branch_id: str | None) -> list[str]:
    ids = scope_branch_ids(db, user)
    all_ids = ids if ids is not None else list(db.execute(select(Branch.id)).scalars())
    if branch_id:
        return [branch_id] if branch_id in all_ids else []
    return all_ids


@router.get("/workload")
def workload(branch_id: str | None = None, user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_db)):
    ids = _branches(db, user, branch_id)
    agents = db.execute(select(User).where(User.role == "agent", User.branch_id.in_(ids)).order_by(User.name)).scalars().all()
    loads = agent_loads(db, [a.id for a in agents])
    unassigned = db.execute(select(func.count()).select_from(Case).where(
        Case.branch_id.in_(ids), Case.assigned_agent_id.is_(None), Case.channel.in_(("FIELD", "TELE")),
        Case.status.notin_(("PAID", "CLOSED", "DISPUTED")))).scalar()
    branches = db.execute(select(Branch).where(Branch.id.in_(ids)).order_by(Branch.name)).scalars().all()
    by_branch = {b.id: b.name for b in branches}
    return {
        "unassigned": unassigned,
        "branches": [{"id": b.id, "name": b.name, "city": b.city} for b in branches],
        "agents": [{"id": a.id, "name": a.name, "branch": by_branch.get(a.branch_id), "branch_id": a.branch_id,
                    "load": loads[a.id], "capacity": a.capacity,
                    "utilisation": round(loads[a.id] / max(a.capacity, 1), 3)} for a in agents],
    }


@router.post("/run")
def run(branch_id: str | None = None, user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_write_db, scope="function")):
    ids = _branches(db, user, branch_id)
    result = allocate(db, ids, user)
    audit.record(db, user, "allocation.run", "allocation", None, {"branches": len(ids), **result})
    return result


@router.post("/rebalance")
def run_rebalance(branch_id: str | None = None, user: User = Depends(require(*MANAGERS)), db: Session = Depends(get_write_db, scope="function")):
    ids = _branches(db, user, branch_id)
    result = rebalance(db, ids, user)
    audit.record(db, user, "allocation.rebalance", "allocation", None, {"branches": len(ids), **result})
    return result
