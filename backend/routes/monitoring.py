# controls whether monitoring is turn on or off for given child

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db,Child

router = APIRouter()

# schema
class ToggleRequest(BaseModel):
    child_id: str
    status: str | None = None

# to toggle status (on/off)
@router.post("/toggle-monitoring")
def toggle_monitoring(
    payload:ToggleRequest,
    db: Session = Depends(get_db)
):
    child = db.query(Child).filter(Child.child_id == payload.child_id).first()

    # create a child if it does not exists.
    if child is None:
        child = Child(child_id = payload.child_id, monitoring_status="on")
        db.add(child)
        db.commit()
        db.refresh(child)  

    if payload.status in ("on","off"):
        child.monitoring_status = payload.status
    else:
        child.monitoring_status = "off" if child.monitoring_status == "on" else "on"

    db.commit()
    db.refresh(child)

    return {
        "child_id":child.child_id,
        "monitoring_status":child.monitoring_status
    }

# extension checks this before sending any data.
@router.get("/monitoring-status")
def monitoring_status(
    child_id = Query(...),
    db: Session = Depends(get_db)
):
    child = db.query(Child).filter(Child.child_id == child_id).first()

    if child_id is None:
        return {"child_id":child_id, "monitoring_status":"on"}

    return {"child_id":child.child_id, "monitoring_status":child.monitoring_status}