import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db, Parent, Child
from core.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------
# schemas
# ---------------------------------------------------------------------

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PairRequest(BaseModel):
    pairing_code: str


# ---------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    parent = db.query(Parent).filter(Parent.email == payload.email).first()

    if parent is None or not verify_password(payload.password, parent.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(parent.id)
    return {"access_token": token, "token_type": "bearer", "parent_id": parent.id}


# Signup isn't explicitly in the spec's file list, but /login has no
# accounts to log into without it — kept minimal (name/email/password
# only) so the login flow above is actually usable end to end.
@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(Parent).filter(Parent.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    parent = Parent(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(parent)
    db.commit()
    db.refresh(parent)

    token = create_access_token(parent.id)
    return {"access_token": token, "token_type": "bearer", "parent_id": parent.id}


# ---------------------------------------------------------------------
# POST /api/auth/pair — extension pairs itself to a parent's child record
# ---------------------------------------------------------------------

@router.post("/pair")
def pair(payload: PairRequest, db: Session = Depends(get_db)):
    child = db.query(Child).filter(Child.pairing_code == payload.pairing_code).first()

    if child is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired pairing code")

    child_id = child.child_id

    # One-time use: rotate the code immediately so it can't be reused.
    child.pairing_code = None
    db.commit()

    return {"child_id": child_id}


def generate_pairing_code() -> str:
    """Used by routes/children.py when creating a new child to link."""
    return secrets.token_urlsafe(6)
