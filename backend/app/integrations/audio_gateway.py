"""Transcripción de audio con Groq; nunca registra audio, texto ni credenciales."""

import logging

import httpx

from app.core.config import get_settings
from app.integrations import llm_gateway

settings = get_settings()
logger = logging.getLogger("mica.audio")
MAX_TRANSCRIPT = 4000


class AudioError(Exception):
    """Mensaje público que se puede enviar sin exponer errores del proveedor."""


def is_enabled() -> bool:
    return bool(
        settings.enable_telegram_audio
        and settings.groq_transcription_model
        and llm_gateway.is_enabled()
    )


def transcribe(content: bytes, filename: str) -> str:
    if not is_enabled():
        raise AudioError(
            "Por ahora no puedo escuchar audios. Escríbeme tu consulta y te ayudaré por aquí."
        )
    if not content or len(content) > settings.telegram_audio_max_bytes:
        raise AudioError("No pude leer ese audio. Envíame uno más pequeño o escríbeme tu consulta.")
    try:
        response = httpx.post(
            f"{settings.groq_base_url.rstrip('/')}/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            files={"file": (filename, content, "application/octet-stream")},
            data={
                "model": settings.groq_transcription_model,
                "language": "es",
                "response_format": "verbose_json",
                "temperature": "0",
            },
            timeout=httpx.Timeout(settings.groq_transcription_timeout_seconds, connect=5.0),
        )
        response.raise_for_status()
        data = response.json()
        duration = data.get("duration", 0)
        if not isinstance(duration, (int, float)) or duration > settings.telegram_audio_max_seconds:
            raise AudioError(
                f"Ese audio es muy largo. Envíame uno de hasta {settings.telegram_audio_max_seconds} segundos o escríbeme tu consulta."
            )
        text = data.get("text")
        if not isinstance(text, str) or not text.strip():
            raise AudioError(
                "No pude distinguir palabras en ese audio. Intenta grabarlo de nuevo con menos ruido o escríbeme tu consulta."
            )
        if len(text.strip()) > MAX_TRANSCRIPT:
            raise AudioError(
                "Ese audio contiene demasiado texto. Divídelo en mensajes más cortos para que pueda entenderlo completo."
            )
        return text.strip()
    except AudioError:
        raise
    except Exception as exc:
        logger.warning("audio.transcription_failed type=%s", type(exc).__name__)
        raise AudioError(
            "No pude transcribir tu audio en este momento. Intenta enviarlo otra vez o escríbeme tu consulta."
        ) from None
