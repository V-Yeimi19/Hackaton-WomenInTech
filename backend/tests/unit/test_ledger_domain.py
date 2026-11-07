"""Pruebas puras de asientos balanceados y clasificación."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.ledger import domain


def _sum(entries) -> Decimal:
    return sum((entry.delta for entry in entries), Decimal("0.00"))


@pytest.mark.parametrize(
    "kind,medium",
    [
        (domain.SALE, domain.DIGITAL),
        (domain.SALE, domain.CASH),
        (domain.BUSINESS_PAYMENT, domain.DIGITAL),
        (domain.BUSINESS_PAYMENT, domain.CASH),
        (domain.UNKNOWN_OUTFLOW, domain.DIGITAL),
    ],
)
def test_entradas_de_operaciones_suman_cero(kind: str, medium: str) -> None:
    entries = domain.entries_for(kind, Decimal("100.00"), medium)
    assert _sum(entries) == Decimal("0.00")


def test_venta_digital_solo_aumenta_bolsillo_negocio() -> None:
    entries = domain.entries_for(domain.SALE, Decimal("120.00"), domain.DIGITAL)
    assert domain.EntryDraft(domain.BUSINESS_DIGITAL, Decimal("120.00")) in entries
    assert domain.EntryDraft(domain.CASH_DECLARED, Decimal("120.00")) not in entries


def test_venta_efectivo_solo_aumenta_caja_declarada() -> None:
    entries = domain.entries_for(domain.SALE, Decimal("120.00"), domain.CASH)
    assert domain.EntryDraft(domain.CASH_DECLARED, Decimal("120.00")) in entries


def test_retiro_mueve_negocio_a_hogar_sin_gasto() -> None:
    entries = domain.entries_for(domain.HOUSEHOLD_WITHDRAWAL, Decimal("100.00"))
    assert entries == [
        domain.EntryDraft(domain.BUSINESS_DIGITAL, Decimal("-100.00")),
        domain.EntryDraft(domain.HOUSEHOLD_DIGITAL, Decimal("100.00")),
    ]


def test_aporte_mueve_hogar_a_negocio() -> None:
    entries = domain.entries_for(domain.OWNER_CONTRIBUTION, Decimal("100.00"))
    assert entries == [
        domain.EntryDraft(domain.HOUSEHOLD_DIGITAL, Decimal("-100.00")),
        domain.EntryDraft(domain.BUSINESS_DIGITAL, Decimal("100.00")),
    ]


def test_apertura_requiere_cuenta_visible() -> None:
    with pytest.raises(domain.LedgerRuleError):
        domain.entries_for(
            domain.OPENING_BALANCE,
            Decimal("300.00"),
            target_account_kind=domain.EXTERNAL_CLEARING,
        )


def test_ajuste_de_clasificacion_no_reduce_negocio_otra_vez() -> None:
    entries = domain.classification_adjustment_entries(Decimal("250.00"), domain.HOUSEHOLD_DIGITAL)
    assert entries == [
        domain.EntryDraft(domain.EXTERNAL_CLEARING, Decimal("-250.00")),
        domain.EntryDraft(domain.HOUSEHOLD_DIGITAL, Decimal("250.00")),
    ]
    assert all(entry.account_kind != domain.BUSINESS_DIGITAL for entry in entries)


def test_reversion_invierte_asientos() -> None:
    entries = domain.reversal_entries(
        [
            (domain.BUSINESS_DIGITAL, Decimal("100.00")),
            (domain.EXTERNAL_CLEARING, Decimal("-100.00")),
        ]
    )
    assert entries == [
        domain.EntryDraft(domain.BUSINESS_DIGITAL, Decimal("-100.00")),
        domain.EntryDraft(domain.EXTERNAL_CLEARING, Decimal("100.00")),
    ]
