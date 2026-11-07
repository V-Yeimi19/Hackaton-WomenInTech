"""DTOs de consentimientos y preferencias."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConsentGrantRequest(BaseModel):
    policy_version: str = "demo-1"
    channel: str = "WEB"
    evidence_ref: str | None = None


class ConsentRevocationRequest(BaseModel):
    policy_version: str | None = None
    reason: str | None = None


class ConsentOut(BaseModel):
    purpose: str
    policy_version: str
    granted_at: datetime
    revoked_at: datetime | None = None
    active: bool


class PreferencesPatch(BaseModel):
    reports_enabled: bool | None = None
    format: Literal["TEXT", "AUDIO"] | None = None
    schedule_local: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    invitations_enabled: bool | None = None


class PreferencesOut(BaseModel):
    reports_enabled: bool
    format: str
    schedule_local: str
    invitations_enabled: bool
    updated_at: datetime
