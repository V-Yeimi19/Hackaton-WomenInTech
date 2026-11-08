"""Configuración común: se carga antes que cualquier módulo de la app."""

import os

# Las pruebas cubren ambos canales del agente (WhatsApp y Telegram).
os.environ.setdefault("WHATSAPP_ENABLED", "true")
os.environ.setdefault("TELEGRAM_ENABLED", "true")
