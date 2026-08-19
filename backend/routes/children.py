from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, Child, Parent
from core.security import get_current_parent
from routes.auth import generate_pairing_code

router = APIRouter(prefix="/api/children", tags=["children"])


class CreateChildRequest(BaseModel):
    child_id: str


@router.get("")
def list_children(
    current_parent: Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    """Needed by the dashboard's home screen and 'Link a child' flow."""
    children = db.query(Child).filter(Child.parent_id == current_parent.id).all()
    return [
        {
            "child_id": c.child_id,
            "monitoring_status": c.monitoring_status,
            "pairing_code": c.pairing_code,  # null once the extension has paired
            "created_at": c.created_at,
        }
        for c in children
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_child(
    payload: CreateChildRequest,
    current_parent: Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    """
    Creates a new child record owned by the logged-in parent, with a
    fresh one-time pairing code — this is what the dashboard's "Link a
    child" screen shows to the parent, and what the extension later
    exchanges via POST /api/auth/pair.
    """
    existing = db.query(Child).filter(Child.child_id == payload.child_id).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="child_id already exists")

    child = Child(
        child_id=payload.child_id,
        parent_id=current_parent.id,
        monitoring_status="on",
        pairing_code=generate_pairing_code(),
    )
    db.add(child)
    db.commit()
    db.refresh(child)

    return {
        "child_id": child.child_id,
        "pairing_code": child.pairing_code,
        "monitoring_status": child.monitoring_status,
    }
