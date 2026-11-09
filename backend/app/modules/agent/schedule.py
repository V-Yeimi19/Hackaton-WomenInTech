"""Horario del reporte semanal a partir de la respuesta libre del perfil de Mica.

"lunes a las 2:10pm", "Viernes a las 6 p. m.", "domingo 20:00" o "martes al
mediodía" se convierten en (día, "HH:MM") con lunes = 0 … domingo = 6.
"""

from __future__ import annotations

import re
import unicodedata
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow

DAYS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "domingo": 6,
}
DAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

TIME = re.compile(
    r"(?<!\d)(?P<hour>\d{1,2})(?:\s*[:.h]\s*(?P<minute>\d{2}))?\s*"
    r"(?P<suffix>a\.?\s*m\.?|p\.?\s*m\.?|hrs?\b|horas?\b)?",
)


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _time(text: str) -> str | None:
    if "mediodia" in text:
        return "12:00"
    if "medianoche" in text:
        return "00:00"
    for match in TIME.finditer(text):
        hour = int(match["hour"])
        minute = int(match["minute"] or 0)
        suffix = (match["suffix"] or "").replace(" ", "").replace(".", "")
        if not match["minute"] and not suffix and "las" not in text[: match.start()][-6:]:
            continue  # un número suelto ("2 veces") no es una hora
        if suffix == "pm" or (
            not suffix.startswith("am") and ("tarde" in text or "noche" in text) and hour < 12
        ):
            hour = hour % 12 + 12
        elif suffix == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    return None


def parse_schedule(text: str) -> tuple[int, str] | None:
    """(día de la semana, "HH:MM") o None si no hay un día y una hora claros."""
    plain = _plain(text or "")
    days = [index for name, index in DAYS.items() if re.search(rf"\b{name}\b", plain)]
    when = _time(plain)
    if len(days) != 1 or when is None:
        return None
    return days[0], when


def describe(weekday: int, hhmm: str) -> str:
    """Texto amable: "lunes a las 2:10 p. m."."""
    hour, minute = map(int, hhmm.split(":"))
    suffix = "a. m." if hour < 12 else "p. m."
    shown = hour % 12 or 12
    return f"{DAY_NAMES[weekday]} a las {shown}:{minute:02d} {suffix}"


REPORT_WORDS = re.compile(r"\b(reporte|resumen|informe|horario)s?\b")
CHANGE_WORDS = re.compile(
    r"\b(cambi\w*|modific\w*|mover\w*|muev\w*|reprogram\w*|otro dia|otra hora)"
)
# Mica pregunta con este texto; si su último mensaje lo empieza, la respuesta
# siguiente se interpreta como el nuevo día y hora.
ASK = "¿Qué día y a qué hora quieres recibir tu reporte semanal?"
ASK_EXAMPLE = " Por ejemplo: jueves a las 3 p. m."


def _asked(last_reply: str | None) -> bool:
    return bool(last_reply) and ASK in (last_reply or "")


def _mentions_day_or_time(plain: str) -> bool:
    return any(re.search(rf"\b{day}\b", plain) for day in DAYS) or bool(
        re.search(r"\d\s*(:|\.|h\b|am|pm|a\.?\s*m|p\.?\s*m)|mediodia|medianoche", plain)
    )


def request_change(
    db: Session, business_id: uuid.UUID, text: str, last_reply: str | None = None
) -> str | None:
    """Conversación para cambiar el horario del reporte semanal desde el chat.

    - "¿puedo cambiarlo?" (hablando del reporte) → Mica pregunta día y hora.
    - La respuesta siguiente ("jueves a las 3pm") → se reprograma y confirma.
    - "mándame el reporte los viernes a las 6pm" → se reprograma directamente.
    Cualquier otro mensaje devuelve None y sigue el flujo normal del agente.
    """
    plain = _plain(text or "")
    parsed = parse_schedule(text)
    about_report = bool(REPORT_WORDS.search(plain)) or (
        bool(last_reply) and "reporte" in _plain(last_reply or "")
    )
    if parsed and (REPORT_WORDS.search(plain) or _asked(last_reply)):
        weekday, hhmm = parsed
        save(db, business_id, weekday, hhmm)
        return (
            f"Listo, tu reporte semanal llegará los {describe(weekday, hhmm)} (hora de Lima). "
            "Si quieres cambiarlo otra vez, solo dímelo."
        )
    if _asked(last_reply) and _mentions_day_or_time(plain):
        # Respondió a la pregunta pero falta el día o la hora.
        return "Me falta el día o la hora. " + ASK + ASK_EXAMPLE
    if about_report and CHANGE_WORDS.search(plain):
        return "Claro. " + ASK + ASK_EXAMPLE
    return None


def save(db: Session, business_id: uuid.UUID, weekday: int, hhmm: str) -> None:
    """Guarda el horario en las preferencias y en la respuesta del perfil de Mica."""
    from app.modules.agent.models import AgentProfile
    from app.modules.consents.models import Preference

    prefs = db.get(Preference, business_id)
    if prefs is None:
        prefs = Preference(business_id=business_id)
        db.add(prefs)
    prefs.schedule_weekday = weekday
    prefs.schedule_local = hhmm
    text = describe(weekday, hhmm)
    for profile in db.scalars(select(AgentProfile).where(AgentProfile.business_id == business_id)):
        if len(profile.answers) > 4 and profile.answers[4] != text:
            profile.answers = [*profile.answers[:4], text, *profile.answers[5:]]
            profile.version += 1
            profile.updated_at = utcnow()
    db.flush()
