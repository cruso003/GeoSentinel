"""Schemas for Phase 2.3 notifications + RBAC endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

SEVERITY = Literal["INFO", "WARNING", "CRITICAL", "EVACUATION"]
CHANNEL = Literal["email", "sms", "push"]


class SubscriptionIn(BaseModel):
    site_id: str
    channel: CHANNEL
    min_severity: SEVERITY = "CRITICAL"
    active: bool = True


class SubscriptionOut(BaseModel):
    id: str
    user_id: str
    site_id: str
    channel: CHANNEL
    min_severity: SEVERITY
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    """Profile fields a user is allowed to edit for themselves. ``role`` and
    ``email`` are intentionally absent — those changes are admin-only."""

    name: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, max_length=20)

    @field_validator("phone_number")
    @classmethod
    def _e164(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip()
        if not v.startswith("+") or not v[1:].isdigit() or not (8 <= len(v[1:]) <= 15):
            raise ValueError("phone_number must be E.164 (e.g. +231881234567)")
        return v


class TestAlertRequest(BaseModel):
    site_id: str
    channel: CHANNEL = "email"
    message: str = Field(default="This is a test alert.", max_length=500)


class SubscriberRowOut(BaseModel):
    """ESG-admin view of one subscribed user-site-channel tuple."""

    user_id: str
    user_email: EmailStr
    user_name: str
    site_id: str
    channel: CHANNEL
    min_severity: SEVERITY
    active: bool
