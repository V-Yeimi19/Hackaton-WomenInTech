"""Voz opcional. Desactivada en P0 (ENABLE_TTS=false)."""

from __future__ import annotations

from app.core.config import get_settings

settings = get_settings()


def synthesize(text: str) -> str | None:
    if not settings.enable_tts:
        return None
    # P1: integrar TTS con almacenamiento temporal y las mismas cifras del snapshot.
    return None
