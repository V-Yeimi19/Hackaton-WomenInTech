"""Reglas puras del libro financiero.

Este módulo no importa FastAPI, SQLAlchemy ni Twilio.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# Cuentas
BUSINESS_DIGITAL = "BUSINESS_DIGITAL"
HOUSEHOLD_DIGITAL = "HOUSEHOLD_DIGITAL"
CASH_DECLARED = "CASH_DECLARED"
EXTERNAL_CLEARING = "EXTERNAL_CLEARING"
ACCOUNT_KINDS = (BUSINESS_DIGITAL, HOUSEHOLD_DIGITAL, CASH_DECLARED, EXTERNAL_CLEARING)
DISPLAY_ACCOUNTS = (BUSINESS_DIGITAL, HOUSEHOLD_DIGITAL, CASH_DECLARED)
# Billeteras con nombre (ahorro y creadas por la usuaria). No forma parte de
# ACCOUNT_KINDS porque no es una cuenta fija: hay una por billetera.
WALLET = "WALLET"
WALLET_CASH = "WALLET_CASH"

# Tipos de operación
SALE = "SALE"
BUSINESS_PAYMENT = "BUSINESS_PAYMENT"
HOUSEHOLD_WITHDRAWAL = "HOUSEHOLD_WITHDRAWAL"
OWNER_CONTRIBUTION = "OWNER_CONTRIBUTION"
UNKNOWN_OUTFLOW = "UNKNOWN_OUTFLOW"
OPENING_BALANCE = "OPENING_BALANCE"
CLASSIFICATION_ADJUSTMENT = "CLASSIFICATION_ADJUSTMENT"
REVERSAL = "REVERSAL"
# Operaciones de billeteras personales (no son métricas del negocio).
PERSONAL_PAYMENT = "PERSONAL_PAYMENT"
PERSONAL_INCOME = "PERSONAL_INCOME"
WALLET_TRANSFER = "WALLET_TRANSFER"

# Medios
DIGITAL = "DIGITAL"
CASH = "CASH"

# Fuentes
SIMULATED = "SIMULATED"
USER_DECLARED = "USER_DECLARED"
PROVIDER_CONFIRMED = "PROVIDER_CONFIRMED"

# Clasificación
EXPLICIT_ACTION = "EXPLICIT_ACTION"
USER_CONFIRMED = "USER_CONFIRMED"
RULE = "RULE"
PENDING = "PENDING"

METRIC_BY_KIND = {
    SALE: "sales",
    BUSINESS_PAYMENT: "payments",
    HOUSEHOLD_WITHDRAWAL: "withdrawals",
    OWNER_CONTRIBUTION: "contributions",
}


class LedgerRuleError(ValueError):
    pass


@dataclass(frozen=True)
class EntryDraft:
    account_kind: str
    delta: Decimal


def entries_for(
    kind: str,
    amount: Decimal,
    medium: str = DIGITAL,
    target_account_kind: str | None = None,
) -> list[EntryDraft]:
    """Devuelve los asientos balanceados de una operación.

    `amount` siempre es positivo; el signo vive en `delta`.
    """
    if amount <= 0:
        raise LedgerRuleError("El importe debe ser positivo")

    if kind == SALE:
        source = BUSINESS_DIGITAL if medium == DIGITAL else CASH_DECLARED
        return [EntryDraft(source, amount), EntryDraft(EXTERNAL_CLEARING, -amount)]

    if kind == BUSINESS_PAYMENT:
        source = BUSINESS_DIGITAL if medium == DIGITAL else CASH_DECLARED
        return [EntryDraft(source, -amount), EntryDraft(EXTERNAL_CLEARING, amount)]

    if kind == HOUSEHOLD_WITHDRAWAL:
        return [EntryDraft(BUSINESS_DIGITAL, -amount), EntryDraft(HOUSEHOLD_DIGITAL, amount)]

    if kind == OWNER_CONTRIBUTION:
        return [EntryDraft(HOUSEHOLD_DIGITAL, -amount), EntryDraft(BUSINESS_DIGITAL, amount)]

    if kind == UNKNOWN_OUTFLOW:
        return [EntryDraft(BUSINESS_DIGITAL, -amount), EntryDraft(EXTERNAL_CLEARING, amount)]

    if kind == OPENING_BALANCE:
        if target_account_kind not in DISPLAY_ACCOUNTS:
            raise LedgerRuleError("La apertura requiere una cuenta destino válida")
        return [EntryDraft(target_account_kind, amount), EntryDraft(EXTERNAL_CLEARING, -amount)]

    raise LedgerRuleError(f"Tipo de operación sin asientos genéricos: {kind}")


def classification_adjustment_entries(
    amount: Decimal, target_account_kind: str
) -> list[EntryDraft]:
    """Mueve la contrapartida externa hacia la cuenta final sin tocar el origen.

    Se usa cuando una salida ambigua del bolsillo negocio se confirma como retiro
    al hogar: EXTERNAL_CLEARING -amount y HOUSEHOLD_DIGITAL +amount.
    """
    if target_account_kind != HOUSEHOLD_DIGITAL:
        raise LedgerRuleError("Solo se admite ajuste hacia HOUSEHOLD_DIGITAL")
    return [EntryDraft(EXTERNAL_CLEARING, -amount), EntryDraft(HOUSEHOLD_DIGITAL, amount)]


def reversal_entries(entries: list[tuple[str, Decimal]]) -> list[EntryDraft]:
    """Invierte exactamente los asientos originales."""
    return [EntryDraft(kind, -delta) for kind, delta in entries]


def is_debit_account(account_kind: str) -> bool:
    """Cuentas cuyo saldo no debe quedar negativo por una operación iniciada."""
    return account_kind in DISPLAY_ACCOUNTS or account_kind in (WALLET, WALLET_CASH)


def metric_name(kind: str) -> str | None:
    return METRIC_BY_KIND.get(kind)
