# Controls whether monitoring is turned on or off for a given child.
#
# SECURITY FIX (spec Section 4.6): toggling monitoring now requires an
# authenticated parent session, AND that parent must own the target
# child (child.parent_id == current_parent.id). Previously this endpoint
# had no auth at all and would silently create a Child row for any
# child_id a caller supplied.

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, Child, Parent
from core.security import get_current_parent

router = APIRouter()


# schema
class ToggleRequest(BaseModel):
    child_id: str
    status: str | None = None


def _get_owned_child(child_id: str, current_parent: Parent, db: Session) -> Child:
    """
    Looks up the child and verifies it belongs to current_parent. Raises
    404 (not 403) for a child that exists but belongs to someone else,
    so we don't leak which child_ids exist to a parent who doesn't own
    them.
    """
    child = db.query(Child).filter(Child.child_id == child_id).first()

    if child is None or child.parent_id != current_parent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")

    return child


# POST /api/monitoring/toggle — auth required, ownership required.
@router.post("/api/monitoring/toggle")
def toggle_monitoring(
    payload: ToggleRequest,
    current_parent: Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    child = _get_owned_child(payload.child_id, current_parent, db)

    if payload.status in ("on", "off"):
        child.monitoring_status = payload.status
    else:
        child.monitoring_status = "off" if child.monitoring_status == "on" else "on"

    db.commit()
    db.refresh(child)

    return {
        "child_id": child.child_id,
        "monitoring_status": child.monitoring_status
    }


# Legacy path, same auth/ownership rules — kept so any existing caller
# doesn't silently start hitting an open endpoint after this change.
@router.post("/toggle-monitoring")
def toggle_monitoring_legacy(
    payload: ToggleRequest,
    current_parent: Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    return toggle_monitoring(payload, current_parent, db)


# GET /monitoring-status — stays OPEN and read-only; the extension calls
# this with no auth to decide whether to collect anything at all.
# (The spec's path-param equivalent, GET /api/monitoring/status/{child_id},
# lives in routes/ingest.py alongside the rest of the signal-ingest
# contract the extension depends on.)
@router.get("/monitoring-status")
def monitoring_status(
    child_id=Query(...),
    db: Session = Depends(get_db)
):
    child = db.query(Child).filter(Child.child_id == child_id).first()

    if child is None:
        return {"child_id": child_id, "monitoring_status": "on"}

    return {"child_id": child.child_id, "monitoring_status": child.monitoring_status}
