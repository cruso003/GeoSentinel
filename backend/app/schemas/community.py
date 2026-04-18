"""Schemas for the public community SMS opt-in endpoints (Phase 2.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _validate_e164_str(v: str) -> str:
    v = v.strip()
    if not v.startswith("+") or not v[1:].isdigit() or not (8 <= len(v[1:]) <= 15):
        raise ValueError("phone_number must be E.164 (e.g. +231881234567)")
    return v


class CommunityOptInRequest(BaseModel):
    phone_number: str = Field(..., max_length=20)
    site_id: str = Field(..., min_length=1, max_length=64)
    language: Literal["en", "mano", "gio"] = "en"

    @field_validator("phone_number")
    @classmethod
    def _e164(cls, v: str) -> str:
        return _validate_e164_str(v)


class CommunityOptInConfirm(BaseModel):
    phone_number: str = Field(..., max_length=20)
    site_id: str = Field(..., min_length=1, max_length=64)
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("phone_number")
    @classmethod
    def _e164(cls, v: str) -> str:
        return _validate_e164_str(v)

    @field_validator("code")
    @classmethod
    def _digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("code must be 6 digits")
        return v


class CommunityOptInResponse(BaseModel):
    """Returned by ``POST /community/subscribe``. ``expires_at`` is the
    deadline by which the caller must redeem the SMS code. ``debug_code`` is
    only populated in dev (no Twilio creds) so smoke-tests can drive the flow
    end-to-end — production responses always leave it ``None``."""

    phone_number: str
    site_id: str
    expires_at: datetime
    debug_code: str | None = None


class CommunityConfirmResponse(BaseModel):
    """Returned by ``POST /community/confirm`` after a successful redemption."""

    user_id: str
    subscription_id: str
