"""Pruebas de Money: Decimal, PEN y dos decimales."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.shared.money import Money, from_cents, money_str


def test_parse_normaliza_a_dos_decimales() -> None:
    money = Money.parse("1500")
    assert money.amount == Decimal("1500.00")
    assert money.currency == "PEN"
    assert money.to_str() == "1500.00"


def test_parse_admite_dos_decimales() -> None:
    assert Money.parse("0.01").amount == Decimal("0.01")
    assert Money.parse("120.50").amount == Decimal("120.50")


@pytest.mark.parametrize("value", ["0", "0.00", "-10.00", "abc", "NaN", "Infinity"])
def test_parse_rechaza_importes_invalidos(value: str) -> None:
    with pytest.raises(AppError) as exc:
        Money.parse(value)
    assert exc.value.code == "INVALID_AMOUNT"


def test_parse_rechaza_mas_de_dos_decimales() -> None:
    with pytest.raises(AppError) as exc:
        Money.parse("10.001")
    assert exc.value.code == "INVALID_AMOUNT"


def test_parse_rechaza_moneda_distinta_de_pen() -> None:
    with pytest.raises(AppError) as exc:
        Money.parse("10.00", "USD")
    assert exc.value.code == "INVALID_CURRENCY"


def test_money_str_none_y_decimal() -> None:
    assert money_str(None) == "0.00"
    assert money_str(Decimal("7.5")) == "7.50"
    assert money_str(7) == "7.00"


def test_from_cents() -> None:
    assert from_cents(1234) == Decimal("12.34")


def test_operaciones_mantienen_decimal() -> None:
    total = Money.parse("100.00") + Money.parse("25.50")
    assert total.amount == Decimal("125.50")
    assert (total - Money.parse("0.50")).amount == Decimal("125.00")
