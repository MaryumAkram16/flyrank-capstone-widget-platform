from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Submission, Widget
from app.services import geo as geo_service


def create(
    db: Session,
    widget: Widget,
    data: dict,
    ip_address: str,
    is_spam: bool,
    geo: "geo_service.GeoResult | None",
    email_sent: bool,
) -> Submission:
    submission = Submission(
        widget_id=widget.id,
        tenant_id=widget.tenant_id,
        data=data,
        ip_address=ip_address,
        is_spam=is_spam,
        geo_country=geo.country if geo else None,
        geo_city=geo.city if geo else None,
        geo_provider=geo.provider if geo else None,
        email_sent=email_sent,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def list_for_widget(db: Session, tenant_id: str, widget_id: str) -> list[Submission]:
    return (
        db.query(Submission)
        .filter(Submission.tenant_id == tenant_id, Submission.widget_id == widget_id)
        .order_by(Submission.created_at.desc())
        .all()
    )


def stats_for_widget(db: Session, tenant_id: str, widget_id: str) -> dict:
    base = db.query(Submission).filter(
        Submission.tenant_id == tenant_id, Submission.widget_id == widget_id
    )
    total = base.count()
    spam_blocked = base.filter(Submission.is_spam.is_(True)).count()
    with_geo = base.filter(Submission.geo_country.isnot(None)).count()

    since = datetime.utcnow() - timedelta(days=7)
    rows = (
        db.query(func.date(Submission.created_at), func.count(Submission.id))
        .filter(
            Submission.tenant_id == tenant_id,
            Submission.widget_id == widget_id,
            Submission.created_at >= since,
        )
        .group_by(func.date(Submission.created_at))
        .all()
    )
    last_7_days = {str(day): count for day, count in rows}

    return {
        "widget_id": widget_id,
        "total": total,
        "spam_blocked": spam_blocked,
        "with_geo": with_geo,
        "last_7_days": last_7_days,
    }
