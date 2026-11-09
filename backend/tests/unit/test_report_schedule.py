"""Interpretación del horario del reporte semanal dicho a Mica."""

import pytest

from app.modules.agent.schedule import describe, parse_schedule


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("lunes a las 2:10pm", (0, "14:10")),
        ("Viernes a las 6 p. m.", (4, "18:00")),
        ("domingo 20:00", (6, "20:00")),
        ("martes al mediodía", (1, "12:00")),
        ("sábado 9am", (5, "09:00")),
        ("miércoles a las 8 de la noche", (2, "20:00")),
        ("jueves 7.30 a. m.", (3, "07:30")),
        ("mándame el reporte los viernes a las 6pm", (4, "18:00")),
    ],
)
def test_parse_schedule(text, expected):
    assert parse_schedule(text) == expected


@pytest.mark.parametrize(
    "text", ["lunes", "a las 3pm", "lunes y martes a las 3pm", "todos los días 2 veces", ""]
)
def test_ambiguous_schedule_is_not_guessed(text):
    assert parse_schedule(text) is None


def test_describe():
    assert describe(0, "14:10") == "lunes a las 2:10 p. m."
    assert describe(6, "09:05") == "domingo a las 9:05 a. m."
    assert describe(3, "00:00") == "jueves a las 12:00 a. m."
