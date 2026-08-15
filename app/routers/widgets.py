from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_tenant
from app.database import get_db
from app.models import Tenant
from app.repositories import widgets_repo
from app.schemas import WidgetCreate, WidgetOut, WidgetUpdate

router = APIRouter(prefix="/api/widgets", tags=["widgets"])


@router.post("", response_model=WidgetOut, status_code=status.HTTP_201_CREATED)
def create_widget(
    payload: WidgetCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    return widgets_repo.create(db, tenant.id, payload)


@router.get("", response_model=list[WidgetOut])
def list_widgets(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    return widgets_repo.list_for_tenant(db, tenant.id)


@router.get("/{widget_id}", response_model=WidgetOut)
def get_widget(
    widget_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    widget = widgets_repo.get_for_tenant(db, tenant.id, widget_id)
    if widget is None:
        # Same 404 whether it doesn't exist or belongs to another tenant —
        # that's the isolation guarantee, not just a convenience.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
    return widget


@router.patch("/{widget_id}", response_model=WidgetOut)
def update_widget(
    widget_id: str,
    payload: WidgetUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    widget = widgets_repo.get_for_tenant(db, tenant.id, widget_id)
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
    return widgets_repo.update(db, widget, payload)


@router.delete("/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_widget(
    widget_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    widget = widgets_repo.get_for_tenant(db, tenant.id, widget_id)
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
    widgets_repo.delete(db, widget)
