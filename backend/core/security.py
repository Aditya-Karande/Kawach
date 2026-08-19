"""
core/security.py
=================
Password hashing + session tokens for parent accounts, and the
get_current_parent FastAPI dependency that every parent-only route
(monitoring toggle, alerts, guardians, children) requires.

This is what closes the gap described in spec Section 4.6: "Only an
authenticated parent session can change it. This should be true at the
API level, not just hidden in the UI."
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db, Parent

# In a real deployment this MUST come from the environment — the
# fallback below is only so the app doesn't crash on a fresh checkout
# with no .env yet. Set JWT_SECRET_KEY in .env before deploying.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-insecure-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 14  # 2 weeks

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(parent_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {"sub": str(parent_id), "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_parent(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Parent:
    """
    Reads the bearer token, validates it, and looks up the parent.
    401s if the token is missing, malformed, expired, or doesn't match a
    real parent — this is the dependency every parent-only route (toggle
    monitoring, alerts, guardians, children) must use.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        parent_id = payload.get("sub")
        if parent_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    parent = db.query(Parent).filter(Parent.id == int(parent_id)).first()
    if parent is None:
        raise credentials_exception

    return parent
