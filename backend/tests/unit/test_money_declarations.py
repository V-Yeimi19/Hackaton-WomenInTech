"""Validación pura de controles y montos antes de modificar el libro."""

import uuid

import pytest

from app.modules.agent.declarations import (
    Reply,
    canonical_numbers,
    is_report,
    normalized,
    number_values,
    parse_opening,
    resolve_wallet,
    spelled_integer,
)
from app.modules.wallets.models import Wallet


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hoy vendí 500 soles", True),
        ("Gasté ochenta soles en efectivo", True),
        ("Vendí quinientos en mi negocio", True),
        ("¿Cómo puedo vender más?", False),
        ("Confirmar", False),
        ("Ayuda.", False),
        ("mi número es 987654321", False),
    ],
)
def test_report_detection_preserves_free_questions(text, expected):
    assert is_report(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0", "0.00"),
        ("cero", "0.00"),
        ("cero soles", "0.00"),
        ("Tenía cien soles", "100.00"),
        ("doscientos treinta y cinco", "235.00"),
        ("mil soles", "1000.00"),
        ("dos mil cien", "2100.00"),
        ("S/ 120.50", "120.50"),
        ("150,25 soles.", "150.25"),
        ("-1", None),
        ("NaN", None),
        ("100 o 200", None),
        ("20.555", None),
        ("9999999999999", None),
    ],
)
def test_opening_is_an_explicit_nonnegative_amount(text, expected):
    assert parse_opening(text) == expected


def test_wallet_ambiguity_is_not_guessed():
    first = Wallet(id=uuid.uuid4(), name="Café", role="BUSINESS", purpose="BUSINESS")
    second = Wallet(id=uuid.uuid4(), name="Tienda", role="CUSTOM", purpose="BUSINESS")
    main = Wallet(id=uuid.uuid4(), name="Principal", role="PRINCIPAL", purpose="PERSONAL")
    assert resolve_wallet([first, second, main], "negocio", None) is None
    assert resolve_wallet([first, second, main], "cafe", None) is first
    assert resolve_wallet([first, second, main], "negocio", second) is second
    assert resolve_wallet([first, second, main], "personal", None) is main


def test_cancel_and_confirm_buttons_have_different_actions():
    reply = Reply(
        "Revisa",
        {
            "id": str(uuid.uuid4()),
            "version": 7,
            "status": "PENDING",
            "actions": ["confirm", "edit", "cancel"],
        },
    )
    buttons = reply.markup()["inline_keyboard"][0]
    assert buttons[0]["callback_data"].startswith("money:c:")
    assert buttons[2]["callback_data"].startswith("money:x:")
    assert len({button["callback_data"] for button in buttons}) == 3
    assert all(len(button["callback_data"].encode()) <= 64 for button in buttons)


def test_confirmation_normalizes_case_and_punctuation():
    assert normalized("  CONFIRMAR. ") == "confirmar"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Gasté veinte soles por dos sacos de azúcar", {"20"}),
        ("Pagué veintidós soles", {"22"}),
        ("Ingresé doscientos treinta y cinco soles", {"235"}),
        ("Gasté un sol", {"1"}),
        ("Pagué veinte soles con cincuenta céntimos", {"20.5"}),
        ("Pagué veinte coma cinco soles", {"20.5"}),
    ],
)
def test_money_values_accept_words_and_exclude_product_quantities(text, expected):
    from decimal import Decimal

    assert number_values(text) == {Decimal(value) for value in expected}


@pytest.mark.parametrize("value", [2, 21, 31, 100, 101, 235, 999, 1000, 2100, 999999])
def test_numeric_concepts_have_equivalent_word_forms(value):
    assert canonical_numbers(spelled_integer(value)) == str(value)
