"""DTOs de identidad y sesión demo."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DemoSessionCreate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    scenario: Literal["empty", "risk", "stable"] = "empty"
    phone: str | None = Field(
        default=None,
        description="Teléfono de prueba autorizado para la demo de WhatsApp.",
        max_length=24,
    )


class DemoSessionResponse(BaseModel):
    session_token: str
    csrf_token: str
    expires_at: datetime
    user_id: UUID
    business_id: UUID | None = None
    environment: str = "DEMO"
    scenario: str = "empty"
    message: str = "Sesión demo creada. Guarda el token; no se vuelve a mostrar."


class ChannelLinkChallengeResponse(BaseModel):
    code: str
    expires_at: datetime
    instructions: str = (
        "Envía por WhatsApp el mensaje 'VINCULAR <código>' al número de prueba configurado."
    )


class PhoneLoginRequest(BaseModel):
    phone: str = Field(min_length=9, max_length=20, description="Celular peruano de 9 dígitos.")


class PhoneLoginResponse(BaseModel):
    session_token: str
    csrf_token: str
    expires_at: datetime
    user_id: UUID
    business_id: UUID
    phone_masked: str
    is_new: bool
    environment: str = "DEMO"


class MeResponse(BaseModel):
    user_id: UUID
    business_id: UUID | None = None
    phone_masked: str | None = None
    environment: str
    session_expires_at: datetime
