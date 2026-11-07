"""DTOs de integración y eventos."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, field_validator

from app.shared.money import Money


class SimulatorEvent(BaseModel):
    schema_version: str = "1.0"
    event_id: str
    event_type: Literal["transaction.confirmed"]
    environment: Literal["DEMO"] = "DEMO"
    external_transaction_id: str
    business_reference: str
    kind: Literal["SALE", "REVERSAL"]
    amount: str
    currency: Literal["PEN"] = "PEN"
    occurred_at: AwareDatetime
    source: Literal["SIMULATED"] = "SIMULATED"
    original_external_transaction_id: str | None = None

    @field_validator("amount")
    @classmethod
    def valid_amount(cls, value: str) -> str:
        return Money.parse(value).to_str()


class SimulatorEventResponse(BaseModel):
    received: bool
    event_id: str
    status: str
    message: str


class MessageOut(BaseModel):
    id: str
    status: str
    provider_sid: str | None = None
