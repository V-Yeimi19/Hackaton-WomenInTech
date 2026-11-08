"""Reglas puras del canal Telegram."""

import pytest

from app.core.security import channel_address, channel_lookup_hash, phone_lookup_hash
from app.modules.messaging.service import parse_telegram_text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/start abc_123-XYZ", ("VINCULAR", "abc_123-XYZ")),
        ("/start", ("AYUDA", "")),
        ("/resumen", ("RESUMEN", "")),
        ("/resumen@MicaNegocioBot", ("RESUMEN", "")),
        ("pausar", ("PAUSAR", "")),
        (" aYuDa. ", ("AYUDA", "")),
        ("RESUMEN.", ("RESUMEN", "")),
        ("ReAnUdAr", ("REANUDAR", "")),
        ("Pausar los reportes mañana", ("", "")),
        ("Resumen de mis gastos", ("", "")),
        ("Ayuda con mis cuentas.", ("", "")),
        ("", ("", "")),
        ("1", ("1", "")),
        ("  /ayuda  ", ("AYUDA", "")),
    ],
)
def test_parse_telegram_text(text, expected):
    assert parse_telegram_text(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("alluda", "Ayuda"),
        ("REZUMEN.", "Resumen"),
        ("pausra", "Pausar"),
        ("reanuda", "Reanudar"),
        ("alluda con mis cuentas", None),
        ("rezumen de gastos.", None),
        ("hola", None),
        ("saldo", None),
        ("Ayuda", None),
        ("", None),
    ],
)
def test_suggest_telegram_option(text, expected):
    from app.modules.messaging.service import suggest_telegram_option

    assert suggest_telegram_option(text) == expected


def test_telegram_help_uses_friendly_options():
    from app.modules.messaging.service import help_text

    text = help_text("telegram")
    assert "Escríbeme una de estas opciones" in text
    assert "comandos" not in text.lower()
    assert "/" not in text and "\\" not in text
    for option in ("Resumen", "Pausar", "Reanudar", "Ayuda"):
        assert option in text


def test_telegram_gateway_sends_clickable_options(monkeypatch):
    from app.integrations import telegram_gateway as gateway

    keyboard = {"keyboard": [["Resumen", "Pausar"], ["Reanudar", "Ayuda"]]}
    sent = []

    class Response:
        def json(self):
            return {"ok": True, "result": {"message_id": 42}}

    def post(url, *, json, timeout):
        sent.append(json)
        return Response()

    monkeypatch.setattr(gateway, "is_live", lambda: True)
    monkeypatch.setattr(gateway.httpx, "post", post)
    result = gateway.send_text("123", "Elige una opción", reply_markup=keyboard)
    assert result.status == "DELIVERED"
    assert sent == [{"chat_id": "123", "text": "Elige una opción", "reply_markup": keyboard}]


def test_whatsapp_lookup_is_unchanged():
    # Los vínculos de WhatsApp ya guardados deben seguir encontrándose.
    assert channel_lookup_hash("twilio", "987654321") == phone_lookup_hash("+51987654321")


def test_telegram_lookup_never_collides_with_phone():
    assert channel_lookup_hash("telegram", "51987654321") != phone_lookup_hash("+51987654321")
    # El chat_id no se normaliza como teléfono peruano.
    assert channel_address("telegram", "987654321") == "987654321"


@pytest.mark.parametrize("raw", ["", "abc", "12 34", "+51987"])
def test_invalid_telegram_chat_id(raw):
    with pytest.raises(ValueError):
        channel_address("telegram", raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("en *Emprendimiento Café* ok", "en Emprendimiento Café ok"),
        ("toca **Transferir**.", "toca Transferir."),
        ("Yapeo a Susan Mar* y Stephen Cuo*", "Yapeo a Susan Mar* y Stephen Cuo*"),
    ],
)
def test_clean_reply_strips_markdown_only(raw, expected):
    from app.modules.agent.service import clean_reply

    assert clean_reply(raw) == expected
