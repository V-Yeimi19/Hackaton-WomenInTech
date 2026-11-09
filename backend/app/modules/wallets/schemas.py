"""DTOs de billeteras, yapeos, transferencias y movimientos."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field


class WalletOut(BaseModel):
    id: UUID
    name: str
    role: Literal["PRINCIPAL", "BUSINESS", "SAVINGS", "CUSTOM"]
    purpose: Literal["PERSONAL", "BUSINESS", "SAVINGS"]
    icon: str | None = None
    color: str | None = None
    is_primary: bool
    is_business: bool
    balance: str
    cash_balance: str | None = None
    combined_balance: str | None = None


class WalletListResponse(BaseModel):
    items: list[WalletOut]
    total: str
    cash_total: str = "0.00"
    combined_total: str | None = None
    unallocated_cash: str = "0.00"
    updated_at: AwareDatetime


class WalletCreate(BaseModel):
    name: str = Field(max_length=60)
    purpose: Literal["BUSINESS", "SAVINGS"]
    icon: str | None = Field(default=None, max_length=24)
    color: str | None = Field(default=None, max_length=16)


class WalletArchiveResponse(BaseModel):
    archived: bool
    wallet_id: UUID
    moved_amount: str
    hidden_movements: int


class WalletTransferRequest(BaseModel):
    from_wallet_id: UUID
    to_wallet_id: UUID
    amount: str
    note: str | None = Field(default=None, max_length=80)


class Counterparty(BaseModel):
    type: Literal["CONTACT", "PHONE", "MERCHANT"]
    name: str = Field(min_length=1, max_length=80)
    phone: str | None = Field(default=None, max_length=20)


class YapeoRequest(BaseModel):
    from_wallet_id: UUID
    amount: str
    counterparty: Counterparty
    category: Literal["RESTOCK", "LOCAL_SERVICES", "FAMILY"] | None = None
    message: str | None = Field(default=None, max_length=80)


class IncomingYapeRequest(BaseModel):
    to_wallet_id: UUID
    amount: str
    from_name: str = Field(min_length=1, max_length=80)


class MovementWallet(BaseModel):
    id: UUID
    name: str
    role: str
    purpose: str
    delta: str


class WalletRef(BaseModel):
    id: UUID
    name: str


class MovementOut(BaseModel):
    """Movimiento visible para la usuaria; también es la constancia."""

    id: UUID
    operation_number: str
    security_code: str
    kind: str
    medium: Literal["DIGITAL", "CASH"] = "DIGITAL"
    direction: Literal["IN", "OUT", "TRANSFER"]
    title: str
    amount: str
    occurred_at: AwareDatetime
    wallets: list[MovementWallet]
    from_wallet: WalletRef | None = None
    to_wallet: WalletRef | None = None
    counterparty_name: str | None = None
    counterparty_phone_masked: str | None = None
    note: str | None = None
    category: str | None = None
    category_label: str | None = None


class MovementListResponse(BaseModel):
    items: list[MovementOut]
    next_cursor: str | None = None


class OperationResponse(BaseModel):
    movement: MovementOut
    wallets: WalletListResponse
