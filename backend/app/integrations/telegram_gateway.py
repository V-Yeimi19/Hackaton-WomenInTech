"""Puerta de salida/entrada de Telegram (Bot API).

Sin ``TELEGRAM_BOT_TOKEN`` no contacta a nadie: genera un id local y marca la
entrega como simulada, igual que el modo ``fake`` de Twilio. Telegram confirma
la entrega en la misma respuesta, por eso el estado queda en ``DELIVERED``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

from app.core.config import get_settings
from app.integrations.twilio_gateway import SendResult

settings = get_settings()
logger = logging.getLogger("mica.telegram")

# La URL de la Bot API lleva el token: httpx la registra completa en nivel INFO.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

API_BASE = "https://api.telegram.org"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
# Telegram corta los mensajes de más de 4096 caracteres.
MAX_TEXT = 4096


def is_live() -> bool:
    return bool(settings.telegram_bot_token)


def _url(method: str) -> str:
    return f"{API_BASE}/bot{settings.telegram_bot_token}/{method}"


def send_text(chat_id: str, body: str, *, reply_markup: dict[str, Any] | None = None) -> SendResult:
    if not is_live():
        return SendResult(
            provider_sid=f"TGDEMO{uuid.uuid4().hex[:24]}", status="DELIVERED", simulated=True
        )
    payload: dict[str, Any] = {"chat_id": chat_id, "text": body[:MAX_TEXT]}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    response = httpx.post(
        _url("sendMessage"),
        json=payload,
        timeout=TIMEOUT,
    )
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram rechazó el envío: {data.get('error_code')}")
    message_id = data["result"]["message_id"]
    return SendResult(provider_sid=f"TG{chat_id}:{message_id}", status="DELIVERED", simulated=False)


def answer_callback_query(callback_query_id: str) -> None:
    """Quita el indicador de carga del botón inline pulsado."""
    if not is_live() or not callback_query_id:
        return
    response = httpx.post(
        _url("answerCallbackQuery"),
        json={"callback_query_id": callback_query_id},
        timeout=TIMEOUT,
    )
    data = response.json()
    if not data.get("ok"):
        logger.warning("telegram.callback_ack_failed code=%s", data.get("error_code"))


def get_updates(offset: int | None) -> list[dict[str, Any]]:
    """Lee mensajes y pulsaciones de botones pendientes (modo polling)."""
    if not is_live():
        return []
    params: dict[str, Any] = {"timeout": 0, "allowed_updates": '["message", "callback_query"]'}
    if offset is not None:
        params["offset"] = offset
    response = httpx.get(_url("getUpdates"), params=params, timeout=TIMEOUT)
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram getUpdates falló: {data.get('error_code')}")
    return list(data.get("result") or [])


def bot_url() -> str | None:
    """Enlace t.me al chat del bot."""
    if not settings.telegram_bot_username:
        return None
    return f"https://t.me/{settings.telegram_bot_username.lstrip('@')}"


def deep_link(code: str) -> str | None:
    """Enlace t.me que abre el bot y envía /start <código> con un toque."""
    base = bot_url()
    return f"{base}?start={code}" if base else None
