from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

WidgetType = Literal["signup_form", "cta_popover"]

# --- Widgets ---------------------------------------------------------------


class WidgetField(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=100)
    type: Literal["text", "email", "textarea", "checkbox"]
    required: bool = False


class WidgetCreate(BaseModel):
    type: WidgetType
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    fields: list[WidgetField] = Field(min_length=1, max_length=20)
    button_text: str = Field(default="Submit", max_length=40)
    display_options: dict = Field(default_factory=dict)


class WidgetUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    fields: list[WidgetField] | None = None
    button_text: str | None = Field(default=None, max_length=40)
    display_options: dict | None = None


class WidgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    title: str
    description: str
    fields: list[WidgetField]
    button_text: str
    display_options: dict
    config_version: int
    bundle_version: str
    created_at: datetime


class WidgetConfigOut(BaseModel):
    """What the public config endpoint returns — no tenant/internal fields."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    title: str
    description: str
    fields: list[WidgetField]
    button_text: str
    display_options: dict
    config_version: int


# --- Submissions -------------------------------------------------------------

# Hard caps so a malicious payload can't blow up the request body or the JSON column.
MAX_FIELD_VALUE_LEN = 2000
MAX_FIELDS = 30


class SubmissionCreate(BaseModel):
    widget_id: str = Field(min_length=1, max_length=64)
    data: dict[str, str] = Field(default_factory=dict)
    # Honeypot: real visitors never fill this (it's hidden via CSS in the widget).
    # A bot filling every field will fill this too.
    website: str = Field(default="", max_length=200)

    @field_validator("data")
    @classmethod
    def bound_data(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > MAX_FIELDS:
            raise ValueError(f"too many fields (max {MAX_FIELDS})")
        for key, val in v.items():
            if len(key) > 100:
                raise ValueError("field name too long")
            if not isinstance(val, str) or len(val) > MAX_FIELD_VALUE_LEN:
                raise ValueError(f"field '{key}' exceeds max length {MAX_FIELD_VALUE_LEN}")
        return v


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    widget_id: str
    data: dict
    geo_country: str | None
    geo_city: str | None
    is_spam: bool
    created_at: datetime


class SubmissionStats(BaseModel):
    widget_id: str
    total: int
    spam_blocked: int
    with_geo: int
    last_7_days: dict[str, int]
