from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db, Child, Guardian, Parent
from core.security import get_current_parent

router = APIRouter(prefix="/api/guardians", tags=["guardians"])


class AddGuardianRequest(BaseModel):
    child_id: str
    email: EmailStr


def _get_owned_child(child_id: str, current_parent: Parent, db: Session) -> Child:
    child = db.query(Child).filter(Child.child_id == child_id).first()
    if child is None or child.parent_id != current_parent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")
    return child


@router.post("", status_code=status.HTTP_201_CREATED)
def add_guardian(
    payload: AddGuardianRequest,
    current_parent: Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    """
    Adds a second guardian email to a child record (spec Section 7.3).
    Tier-3 alert emails go here too, in addition to the primary parent —
    see services/email.py:send_tier3_alert_email.
    """
    child = _get_owned_child(payload.child_id, current_parent, db)

    guardian = Guardian(child_id=child.id, email=payload.email)
    db.add(guardian)
    db.commit()
    db.refresh(guardian)

    return {"id": guardian.id, "child_id": payload.child_id, "email": guardian.email}


@router.get("/{child_id}")
def list_guardians(
    child_id: str,
    current_parent: Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    child = _get_owned_child(child_id, current_parent, db)
    guardians = db.query(Guardian).filter(Guardian.child_id == child.id).all()
    return [{"id": g.id, "email": g.email} for g in guardians]
