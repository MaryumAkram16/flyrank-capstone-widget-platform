import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class SignupResponse(BaseModel):
    tenant_id: str
    api_key: str


def _hash(password: str) -> str:
    # Simple, dependency-free hash — fine for a local capstone demo.
    # A real deployment would use bcrypt/argon2 (noted in README limitations).
    return hashlib.sha256(password.encode()).hexdigest()


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(Tenant).filter(Tenant.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    tenant = Tenant(email=payload.email, hashed_password=_hash(payload.password))
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return SignupResponse(tenant_id=tenant.id, api_key=tenant.api_key)
