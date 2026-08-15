import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    api_key: Mapped[str] = mapped_column(String, unique=True, index=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    widgets: Mapped[list["Widget"]] = relationship(back_populates="tenant")


class Widget(Base):
    __tablename__ = "widgets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    type: Mapped[str] = mapped_column(String)  # "signup_form" | "cta_popover"
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    fields: Mapped[list] = mapped_column(JSON, default=list)
    button_text: Mapped[str] = mapped_column(String, default="Submit")
    display_options: Mapped[dict] = mapped_column(JSON, default=dict)
    config_version: Mapped[int] = mapped_column(Integer, default=1)
    bundle_version: Mapped[str] = mapped_column(String, default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="widgets")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="widget")

    __table_args__ = (Index("ix_widgets_tenant_id_id", "tenant_id", "id"),)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    widget_id: Mapped[str] = mapped_column(ForeignKey("widgets.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String, index=True)  # denormalized from widget
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String, default="")
    geo_country: Mapped[str | None] = mapped_column(String, nullable=True)
    geo_city: Mapped[str | None] = mapped_column(String, nullable=True)
    geo_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    widget: Mapped["Widget"] = relationship(back_populates="submissions")

    __table_args__ = (
        Index("ix_submissions_tenant_widget_created", "tenant_id", "widget_id", "created_at"),
    )
