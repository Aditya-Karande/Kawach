import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, Child, Parent, to_utc_iso
from core.security import get_current_parent
from routes.auth import generate_pairing_code

router = APIRouter(prefix="/api/children", tags=["children"])


class CreateChildRequest(BaseModel):
    name: str
    age: int | None = None


def generate_child_id() -> str:
    """
    child_id is now an internal identifier, generated server-side —
    the parent only ever types a name. Kept human-debuggable (a
    "child_" prefix) but the random suffix is what actually guarantees
    uniqueness, so we don't have to trust the client for it.
    """
    return f"child_{secrets.token_urlsafe(6)}"


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
            "name": c.name,
            "age": c.age,
            "monitoring_status": c.monitoring_status,
            "pairing_code": c.pairing_code,  # null once the extension has paired
            "created_at": to_utc_iso(c.created_at),
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
    Creates a new child record owned by the logged-in parent. The parent
    only supplies a name (+ optional age) — child_id is generated here,
    not by the caller, and handed back in the response along with a
    fresh one-time pairing code for the "Link a child" screen.
    """
    child_id = generate_child_id()
    # Practically impossible to collide (48 bits of randomness), but
    # loop just in case rather than trusting that blindly.
    while db.query(Child).filter(Child.child_id == child_id).first() is not None:
        child_id = generate_child_id()

    child = Child(
        child_id=child_id,
        name=payload.name,
        age=payload.age,
        parent_id=current_parent.id,
        monitoring_status="on",
        pairing_code=generate_pairing_code(),
    )
    db.add(child)
    db.commit()
    db.refresh(child)

    return {
        "child_id": child.child_id,
        "name": child.name,
        "age": child.age,
        "pairing_code": child.pairing_code,
        "monitoring_status": child.monitoring_status,
    }
