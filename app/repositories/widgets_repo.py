from sqlalchemy.orm import Session

from app.models import Widget
from app.schemas import WidgetCreate, WidgetUpdate


def create(db: Session, tenant_id: str, payload: WidgetCreate) -> Widget:
    widget = Widget(
        tenant_id=tenant_id,
        type=payload.type,
        title=payload.title,
        description=payload.description,
        fields=[f.model_dump() for f in payload.fields],
        button_text=payload.button_text,
        display_options=payload.display_options,
    )
    db.add(widget)
    db.commit()
    db.refresh(widget)
    return widget


def list_for_tenant(db: Session, tenant_id: str) -> list[Widget]:
    return db.query(Widget).filter(Widget.tenant_id == tenant_id).all()


def get_for_tenant(db: Session, tenant_id: str, widget_id: str) -> Widget | None:
    """Tenant-scoped lookup — a widget from another tenant simply doesn't exist here."""
    return (
        db.query(Widget)
        .filter(Widget.tenant_id == tenant_id, Widget.id == widget_id)
        .first()
    )


def get_public(db: Session, widget_id: str) -> Widget | None:
    """Unscoped lookup for the public config/delivery path — anyone with the
    id can fetch config (that's the point of an embeddable widget), but they
    can never reach owner-only fields (see schemas.WidgetConfigOut)."""
    return db.query(Widget).filter(Widget.id == widget_id).first()


def update(db: Session, widget: Widget, payload: WidgetUpdate) -> Widget:
    data = payload.model_dump(exclude_unset=True)
    if "fields" in data and data["fields"] is not None:
        data["fields"] = [f if isinstance(f, dict) else f.model_dump() for f in data["fields"]]
    for key, value in data.items():
        setattr(widget, key, value)
    if data:
        widget.config_version += 1
    db.commit()
    db.refresh(widget)
    return widget


def delete(db: Session, widget: Widget) -> None:
    db.delete(widget)
    db.commit()
