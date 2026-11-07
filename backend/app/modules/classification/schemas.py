"""DTOs de resolución de clasificación."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.modules.ledger.schemas import TransactionOut


class ResolutionRequest(BaseModel):
    option: Literal["BUSINESS_PAYMENT", "HOUSEHOLD_WITHDRAWAL"]
    expected_version: int


class ResolutionResponse(BaseModel):
    transaction: TransactionOut
    status: str
    version: int
    message: str
