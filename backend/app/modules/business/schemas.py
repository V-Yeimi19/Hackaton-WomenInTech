"""DTOs de activación, negocio y saldos."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ActivationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: str | None = Field(default=None, max_length=120)
    consent_core: bool
    consent_whatsapp: bool = False
    consent_invitations: bool = False
    policy_version: str = "demo-1"
    channel: str = "WEB"


class BusinessOut(BaseModel):
    id: UUID
    name: str
    category: str | None = None
    status: str
    timezone: str
    currency: str
    environment: str


class ActivationResponse(BaseModel):
    business: BusinessOut
    qr_token: str
    qr_url: str
    accounts: dict[str, str]
    whatsapp_consent: bool


class BalancesResponse(BaseModel):
    business_digital: str
    household_digital: str
    cash_declared: str
    currency: str = "PEN"
    environment: str = "DEMO"
    updated_at: datetime
