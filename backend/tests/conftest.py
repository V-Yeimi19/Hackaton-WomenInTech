"""Configuración común: se carga antes que cualquier módulo de la app."""

import os

# Las pruebas cubren ambos canales del agente (WhatsApp y Telegram).
os.environ.setdefault("WHATSAPP_ENABLED", "true")
os.environ.setdefault("TELEGRAM_ENABLED", "true")
# Nunca usar credenciales reales del .env en pruebas: Telegram y la IA se simulan.
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_BOT_USERNAME"] = ""
os.environ["TELEGRAM_WEBHOOK_SECRET"] = ""
os.environ["ENABLE_LLM"] = "false"
os.environ["GROQ_API_KEY"] = ""
