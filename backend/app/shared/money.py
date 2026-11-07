"""Dinero con Decimal. Nunca usar float para importes financieros."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.core.errors import AppError

CENTS = Decimal("0.01")
SUPPORTED_CURRENCY = "PEN"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = SUPPORTED_CURRENCY

    @classmethod
    def parse(cls, value: object, currency: str = SUPPORTED_CURRENCY) -> Money:
        if currency != SUPPORTED_CURRENCY:
            raise AppError(
                "INVALID_CURRENCY",
                "La única moneda admitida en P0 es PEN.",
                422,
                {"currency": currency},
            )
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise AppError("INVALID_AMOUNT", "Importe inválido.", 422) from exc
        if not decimal_value.is_finite():
            raise AppError("INVALID_AMOUNT", "El importe debe ser finito.", 422)
        if decimal_value <= 0:
            raise AppError("INVALID_AMOUNT", "El importe debe ser mayor que cero.", 422)
        exponent = decimal_value.as_tuple().exponent
        if not isinstance(exponent, int) or exponent < -2:
            raise AppError(
                "INVALID_AMOUNT",
                "El importe admite como máximo dos decimales.",
                422,
            )
        if decimal_value > Decimal("999999999999.99"):
            raise AppError("INVALID_AMOUNT", "El importe supera NUMERIC(14,2).", 422)
        return cls(decimal_value.quantize(CENTS), SUPPORTED_CURRENCY)

    @classmethod
    def zero(cls) -> Money:
        return cls(Decimal("0.00"), SUPPORTED_CURRENCY)

    def to_str(self) -> str:
        return f"{self.amount:.2f}"

    def __add__(self, other: Money) -> Money:
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)


def money_str(value: Decimal | int | float | None) -> str:
    """Formatea un Decimal (o None) a dos decimales, sin float en la entrada."""
    if value is None:
        return "0.00"
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"{value:.2f}"


def from_cents(cents: int) -> Decimal:
    return (Decimal(cents) / Decimal(100)).quantize(CENTS)
