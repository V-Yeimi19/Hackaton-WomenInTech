"""Periodos inclusivos de negocio; nunca se adivina una fecha ambigua."""

import calendar
import re
from datetime import date, timedelta
from decimal import Decimal

from app.modules.agent.declarations import normalized, parse_opening

MONTHS = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
COUNTED_DAYS = re.compile(r"\bultimos?\s+(.+?)\s+dias?\b")


def period(text: str, today: date) -> tuple[date, date] | None:
    text = normalized(text)
    names = "|".join(MONTHS)
    dates = re.findall(r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{4})\b", text)
    named_dates = re.findall(rf"\b(\d{{1,2}}) de ({names})(?: de (\d{{4}}))?\b", text)
    rolling = COUNTED_DAYS.search(text)
    start = end = None
    try:
        if dates:
            if len(dates) > 2:
                raise ValueError("Indica una fecha o un rango de dos fechas.")
            parsed = []
            for value in dates:
                if "/" in value:
                    d, m, y = map(int, value.split("/"))
                else:
                    y, m, d = map(int, value.split("-"))
                parsed.append(date(y, m, d))
            start, end = parsed[0], parsed[-1]
            if len(parsed) == 1 and re.search(r"\bdesde\b", text):
                end = today
        elif len(named_dates) >= 2:
            if len(named_dates) > 2:
                raise ValueError("Indica solo dos fechas.")
            parsed = [
                date(int(y or today.year), MONTHS.index(m) + 1, int(d)) for d, m, y in named_dates
            ]
            start, end = parsed
        elif rolling:
            parsed_count = parse_opening(re.sub(r"\bveintiun\b", "veintiuno", rolling[1]))
            amount = Decimal(parsed_count) if parsed_count is not None else None
            if amount is None or amount != amount.to_integral_value() or not 1 <= amount <= 366:
                raise ValueError("Elige un número entero entre 1 y 366 días, en cifras o palabras.")
            start, end = today - timedelta(days=int(amount) - 1), today
        elif "anteayer" in text:
            start = end = today - timedelta(days=2)
        elif re.search(r"\bayer\b", text):
            start = end = today - timedelta(days=1)
        elif re.search(r"\bhoy\b", text):
            start = end = today
        elif "semana pasada" in text or "semana anterior" in text:
            end = today - timedelta(days=today.weekday() + 1)
            start = end - timedelta(days=6)
        elif "esta semana" in text or "semana actual" in text:
            start, end = today - timedelta(days=today.weekday()), today
        elif "mes pasado" in text or "mes anterior" in text:
            end = today.replace(day=1) - timedelta(days=1)
            start = end.replace(day=1)
        elif "este mes" in text or "mes actual" in text:
            start, end = today.replace(day=1), today
        elif "este ano" in text or "ano actual" in text:
            start, end = today.replace(month=1, day=1), today
        elif "ano pasado" in text or "ano anterior" in text:
            start, end = date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
        else:
            match = re.search(
                rf"\b(?:(\d{{1,2}})\s+(?:al|a|hasta el)\s+)?(?:(\d{{1,2}})\s+de\s+)?({names})(?:\s+(?:de\s+)?(\d{{4}}))?\b",
                text,
            )
            if match:
                month = MONTHS.index(match[3]) + 1
                year = int(match[4] or today.year)
                if match[2]:
                    start = date(year, month, int(match[1] or match[2]))
                    end = date(year, month, int(match[2]))
                else:
                    start = date(year, month, 1)
                    end = date(year, month, calendar.monthrange(year, month)[1])
                if start <= today < end:
                    end = today
    except (OverflowError, ValueError) as exc:
        raise ValueError(
            "Revisa las fechas. Usa, por ejemplo, del 01/10/2026 al 31/10/2026."
        ) from exc
    if start is None or end is None:
        return None
    if start > end:
        raise ValueError("La fecha inicial debe ser anterior o igual a la final.")
    if end > today:
        raise ValueError("El resumen solo puede incluir días hasta hoy.")
    if (end - start).days >= 366:
        raise ValueError("Elige un periodo de hasta 366 días.")
    return start, end
