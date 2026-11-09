"""Datos extraídos: se validan antes de preparar cualquier confirmación."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.money import Money, money_str


class ReportEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wallet: str = Field(max_length=80)
    medium: Literal["CASH", "DIGITAL", "UNKNOWN"]
    direction: Literal["IN", "OUT"]
    amount: str
    description: str = Field(min_length=1, max_length=100)
    evidence: str = Field(min_length=1, max_length=4000)
    day: date | None = None

    @field_validator("amount")
    @classmethod
    def money(cls, value: str) -> str:
        return money_str(Money.parse(value).amount)


class ReportTotal(BaseModel):
    wallet: str
    amount: str

    @field_validator("amount")
    @classmethod
    def money(cls, value: str) -> str:
        return money_str(Money.parse(value).amount)


class ExtractedReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["record", "question"]
    entries: list[ReportEntry] = Field(default_factory=list, max_length=6)
    reported_sales_totals: list[ReportTotal] = Field(default_factory=list, max_length=6)
    questions: list[str] = Field(default_factory=list, max_length=6)


class DeclarationAction(BaseModel):
    id: UUID
    version: int = Field(ge=1)
    action: Literal["confirm", "edit", "cancel"]


class DeclarationState(BaseModel):
    id: UUID
    version: int
    status: str
    actions: list[Literal["confirm", "edit", "cancel"]]


class DeclarationPreview(BaseModel):
    reply: str
    declaration: DeclarationState


class MoneyFact(BaseModel):
    wallet_id: UUID
    wallet_name: str
    medium: Literal["CASH", "DIGITAL"]
    direction: Literal["IN", "OUT"]
    amount: str
    description: str
    day: date
    registered_digital_total: str | None = None


class ConfirmedDeclaration(BaseModel):
    id: UUID
    confirmed_at: datetime
    entries: list[MoneyFact]


class DeclarationMemory(BaseModel):
    pending: DeclarationPreview | None
    latest_confirmed: ConfirmedDeclaration | None
