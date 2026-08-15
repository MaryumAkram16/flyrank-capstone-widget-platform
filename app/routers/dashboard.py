from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_tenant
from app.database import get_db
from app.models import Tenant
from app.repositories import submissions_repo, widgets_repo
from app.schemas import SubmissionOut, SubmissionStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _owned_widget_or_404(db: Session, tenant: Tenant, widget_id: str):
    widget = widgets_repo.get_for_tenant(db, tenant.id, widget_id)
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
    return widget


@router.get("/widgets/{widget_id}/submissions", response_model=list[SubmissionOut])
def list_submissions(
    widget_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    _owned_widget_or_404(db, tenant, widget_id)
    return submissions_repo.list_for_widget(db, tenant.id, widget_id)


@router.get("/widgets/{widget_id}/stats", response_model=SubmissionStats)
def widget_stats(
    widget_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    _owned_widget_or_404(db, tenant, widget_id)
    return submissions_repo.stats_for_widget(db, tenant.id, widget_id)
