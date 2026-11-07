"""DTOs del libro financiero y comandos monetarios."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field


class PaymentRequest(BaseModel):
    amount: str
    currency: str = "PEN"
    provider: str = Field(default="Proveedor Demo", max_length=120)
    description: str | None = None
    commitment_id: UUID | None = None
    ambiguous: bool = False
    occurred_at: AwareDatetime | None = None


class PaymentResponse(BaseModel):
    transaction_id: UUID
    status: str
    environment: str
    kind: str
    amount: str
    balances: dict[str, str]
    classification_request_id: UUID | None = None
    message: str


class TransferRequest(BaseModel):
    amount: str
    currency: str = "PEN"
    direction: Literal["BUSINESS_TO_HOME", "HOME_TO_BUSINESS"]
    occurred_at: AwareDatetime | None = None


class TransferResponse(BaseModel):
    transaction_id: UUID
    status: str
    environment: str
    kind: str
    amount: str
    balances: dict[str, str]
    message: str


class CashRecordRequest(BaseModel):
    type: Literal["SALE", "BUSINESS_PAYMENT"]
    amount: str
    currency: str = "PEN"
    occurred_at: AwareDatetime | None = None
    description: str | None = None


class CashRecordResponse(BaseModel):
    transaction_id: UUID
    status: str
    environment: str
    kind: str
    amount: str
    balances: dict[str, str]
    message: str


class ReplacementIn(BaseModel):
    amount: str
    currency: str = "PEN"
    medium: Literal["DIGITAL", "CASH"] = "DIGITAL"
    occurred_at: AwareDatetime | None = None
    description: str | None = None


class CorrectionRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    replacement: ReplacementIn | None = None


class TransactionOut(BaseModel):
    id: UUID
    kind: str
    amount: str
    currency: str
    medium: str = "DIGITAL"
    status: str
    source: str
    environment: str
    classification_source: str
    occurred_at: AwareDatetime
    description: str | None = None
    reversal_of: UUID | None = None
    replacement_for: UUID | None = None
    adjustment_of: UUID | None = None


class TransactionListResponse(BaseModel):
    items: list[TransactionOut]
    next_cursor: str | None = None


class CorrectionResponse(BaseModel):
    original: TransactionOut
    reversal: TransactionOut
    replacement: TransactionOut | None = None
    message: str
