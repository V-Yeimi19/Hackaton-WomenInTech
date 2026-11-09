from datetime import date, timedelta

import pytest

from app.modules.agent.dashboard_periods import period

TODAY = date(2026, 11, 8)


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        ("PDF de HOY.", "2026-11-08", "2026-11-08"),
        ("ayer", "2026-11-07", "2026-11-07"),
        ("esta semana", "2026-11-02", "2026-11-08"),
        ("semana pasada", "2026-10-26", "2026-11-01"),
        ("este mes", "2026-11-01", "2026-11-08"),
        ("mes pasado", "2026-10-01", "2026-10-31"),
        ("últimos 7 días", "2026-11-02", "2026-11-08"),
        ("del 01/10/2026 al 31/10/2026", "2026-10-01", "2026-10-31"),
        ("2026-11-01 a 2026-11-07", "2026-11-01", "2026-11-07"),
        ("del 1 al 5 de noviembre", "2026-11-01", "2026-11-05"),
        ("octubre de 2026", "2026-10-01", "2026-10-31"),
        ("noviembre", "2026-11-01", "2026-11-08"),
        ("del 1 de octubre al 5 de noviembre", "2026-10-01", "2026-11-05"),
        ("desde 01/11/2026 hasta hoy", "2026-11-01", "2026-11-08"),
        ("este año", "2026-01-01", "2026-11-08"),
        ("año pasado", "2025-01-01", "2025-12-31"),
        ("29 de febrero de 2024", "2024-02-29", "2024-02-29"),
    ],
)
def test_periods_in_business_timezone(text, start, end):
    assert period(text, TODAY) == (date.fromisoformat(start), date.fromisoformat(end))


@pytest.mark.parametrize(
    "text",
    [
        "31/02/2026",
        "2026-11-09",
        "del 08/11/2026 al 01/11/2026",
        "últimos 0 días",
        "últimos 367 días",
        "del 01/01/2020 al 01/01/2026",
    ],
)
def test_invalid_future_reversed_or_excessive_periods(text):
    with pytest.raises(ValueError):
        period(text, TODAY)


def test_unspecified_period_requires_question():
    assert period("Dame un PDF de mi negocio", TODAY) is None


@pytest.mark.parametrize(
    ("number", "count"),
    [
        ("un", 1),
        ("uno", 1),
        ("dos", 2),
        ("tres", 3),
        ("siete", 7),
        ("diez", 10),
        ("quince", 15),
        ("dieciséis", 16),
        ("veintiuno", 21),
        ("veintiún", 21),
        ("veintidós", 22),
        ("treinta y uno", 31),
        ("cien", 100),
        ("ciento veinte", 120),
        ("doscientos treinta y cinco", 235),
        ("trescientos sesenta y seis", 366),
        ("2", 2),
    ],
)
def test_spelled_out_days_match_numeric_period(number, count):
    expected = (TODAY - timedelta(days=count - 1), TODAY)
    assert period(f"PDF de los últimos {number} días", TODAY) == expected
    assert period(f"ÚLTIMOS {number.upper()} DÍAS.", TODAY) == expected
    assert period(f"últimos {number} días hasta hoy", TODAY) == expected


@pytest.mark.parametrize(
    "number", ["cero", "trescientos sesenta y siete", "-2", "2.5", "dos o tres"]
)
def test_invalid_spelled_out_day_counts_require_clarification(number):
    with pytest.raises(ValueError):
        period(f"PDF de los últimos {number} días", TODAY)


def test_spelled_out_period_does_not_become_a_movement_search_term():
    from app.modules.agent.movement_context import criteria

    assert criteria("¿Cuánto gasté en los últimos dos días?") == ((), ())
    assert criteria("mercadería últimos dos días")[1] == ("RESTOCK",)
