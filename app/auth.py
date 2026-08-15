from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant


def get_tenant_by_key(db: Session, api_key: str | None) -> Tenant | None:
    if not api_key:
        return None
    return db.query(Tenant).filter(Tenant.api_key == api_key).first()


def get_current_tenant(
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Tenant:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header"
        )
    tenant = get_tenant_by_key(db, x_api_key)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return tenant

