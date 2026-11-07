"""DTOs de compromisos de pago."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field


class CommitmentCreate(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    amount: str
    currency: str = "PEN"
    payment_account_id: UUID | None = None
    medium: Literal["DIGITAL", "CASH"] = "DIGITAL"
    due_at: AwareDatetime
    confirmed: bool = True


class CommitmentOut(BaseModel):
    id: UUID
    label: str
    amount: str
    due_at: AwareDatetime
    source: str
    status: str
    payment_account_id: UUID
    paid_transaction_id: UUID | None = None


class CommitmentListResponse(BaseModel):
    items: list[CommitmentOut]
