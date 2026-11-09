"""Resumen de ventas del día: intención, meta declarada y hora más movida."""

from datetime import datetime
from decimal import Decimal

import pytest

from app.modules.agent.daily_summary import _busiest_window, declared_daily_sales, wants_summary


@pytest.mark.parametrize(
    "text",
    [
        "Dame el resumen de mis ventas de hoy",
        "¿cuánto vendí hoy?",
        "cómo me fue hoy",
        "resumen del día",
    ],
)
def test_detects_daily_summary(text):
    assert wants_summary(text)


@pytest.mark.parametrize(
    "text",
    [
        "resumen de la semana",
        "hola mica",
        "dame tips para vender más",
        "Hoy vendí 500 soles en mi negocio, 300 fueron en Yape y 200 en efectivo",
        "hoy vendí bastante",
    ],
)
def test_ignores_other_messages(text):
    assert not wants_summary(text)


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("S/ 200", "200"), ("300 soles", "300"), ("entre 200 y 400", "300"), ("S/ 1,500", "1500")],
)
def test_declared_daily_sales(answer, expected):
    assert declared_daily_sales(answer) == Decimal(expected)


def test_declared_daily_sales_needs_a_number():
    assert declared_daily_sales("no sé") is None


def test_busiest_window_picks_the_densest_two_hours():
    day = datetime(2026, 11, 9)
    times = [day.replace(hour=h, minute=m) for h, m in [(8, 30), (9, 0), (9, 50), (15, 0)]]
    assert _busiest_window(times) == (times[0], times[2])
    assert _busiest_window(times[:1]) is None
