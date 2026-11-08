"""Puerta de salida/entrada de Telegram (Bot API).

Sin ``TELEGRAM_BOT_TOKEN`` no contacta a nadie: genera un id local y marca la
entrega como simulada, igual que el modo ``fake`` de Twilio. Telegram confirma
la entrega en la misma respuesta, por eso el estado queda en ``DELIVERED``.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from pathlib import PurePosixPath
from typing import Any

import httpx

from app.core.config import get_settings
from app.integrations.audio_gateway import AudioError
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


def download_audio(file_id: str) -> tuple[bytes, str]:
    """Descarga acotada en memoria, sin seguir URLs ni nombres enviados por el usuario."""
    try:
        response = httpx.get(_url("getFile"), params={"file_id": file_id}, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise ValueError("getFile rejected")
        file = data["result"]
        limit = settings.telegram_audio_max_bytes
        if file.get("file_size", 0) > limit:
            raise AudioError(
                "Ese audio es muy pesado. Envíame uno más pequeño o escríbeme tu consulta."
            )
        path = file["file_path"]
        if (
            not isinstance(path, str)
            or not re.fullmatch(r"[A-Za-z0-9_./-]+", path)
            or path.startswith("/")
            or any(p in (".", "..") for p in path.split("/"))
        ):
            raise ValueError("Invalid Telegram file path")
        extension = PurePosixPath(path).suffix.lower()
        if extension == ".oga":
            extension = ".ogg"
        if extension not in {
            ".ogg",
            ".mp3",
            ".m4a",
            ".mp4",
            ".mpeg",
            ".mpga",
            ".flac",
            ".wav",
            ".webm",
        }:
            raise AudioError(
                "No puedo leer ese formato de audio. Prueba enviándolo como nota de voz de Telegram."
            )
        deadline = time.monotonic() + 20
        with httpx.stream(
            "GET",
            f"{API_BASE}/file/bot{settings.telegram_bot_token}/{path}",
            timeout=httpx.Timeout(20.0, connect=5.0),
            follow_redirects=False,
        ) as stream:
            stream.raise_for_status()
            if int(stream.headers.get("content-length", "0")) > limit:
                raise AudioError(
                    "Ese audio es muy pesado. Envíame uno más pequeño o escríbeme tu consulta."
                )
            content = bytearray()
            for chunk in stream.iter_bytes(chunk_size=64 * 1024):
                if len(content) + len(chunk) > limit:
                    raise AudioError(
                        "Ese audio es muy pesado. Envíame uno más pequeño o escríbeme tu consulta."
                    )
                if time.monotonic() > deadline:
                    raise TimeoutError("Audio download timed out")
                content.extend(chunk)
        if not content:
            raise ValueError("Empty audio")
        return bytes(content), "audio" + extension
    except AudioError:
        raise
    except Exception as exc:
        logger.warning("telegram.audio_download_failed type=%s", type(exc).__name__)
        raise AudioError(
            "No pude descargar ese audio. Intenta enviarlo otra vez o escríbeme tu consulta."
        ) from None
