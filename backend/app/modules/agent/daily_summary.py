"""Resumen de ventas del día en el chat de Mica, con cifras calculadas aquí.

La IA no interviene: los montos, la cantidad de yapeos y la hora más movida
salen de los movimientos de la billetera; la meta, de la venta diaria que la
usuaria le contó a Mica. Se devuelve en Markdown (la app lo muestra como
tarjeta: la cita ">" es el recuadro).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.agent.models import AgentProfile
from app.modules.business.models import Business
from app.modules.wallets import service as wallets_service
from app.modules.wallets.models import Wallet
from app.shared.clock import now_utc, to_business
from app.shared.money import money_str

INTENT = re.compile(
    r"(resumen|reporte|balance).{0,30}\b(hoy|del dia|diario)\b"
    r"|\b(ventas|cobros) de hoy\b"
    r"|\b(cuanto|como|que tal)\b.{0,25}\b(vendi|cobre|vend[oi]|me fue|voy|me va)\b.{0,20}\bhoy\b"
    r"|\b(cuanto|como|que tal)\b.{0,10}\bhoy\b.{0,20}\b(vendi|cobre|ventas)\b"
)
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def wants_summary(text: str) -> bool:
    """Pregunta por el resumen del día. Un mensaje con montos ("hoy vendí 500…") es una
    declaración de ventas y la atiende el flujo de confirmación, no el resumen."""
    plain = _plain(text or "")
    return not any(ch.isdigit() for ch in plain) and bool(INTENT.search(plain))


def declared_daily_sales(answer: str) -> Decimal | None:
    """ "S/ 200", "300 soles", "entre 200 y 400" (promedio) → monto; si no, None."""
    values = []
    for raw in NUMBER.findall(answer or ""):
        normalized = re.sub(r"[.,](?=\d{3}(?:[.,]|$))", "", raw).replace(",", ".")
        try:
            values.append(Decimal(normalized))
        except ArithmeticError:
            return None
    if not values or len(values) > 2 or any(v <= 0 for v in values):
        return None
    return sum(values, Decimal("0")) / len(values)


def _soles(value: Decimal) -> str:
    return f"S/ {money_str(value)}"


def _goal(value: Decimal) -> str:
    """Meta redonda sin decimales: "S/ 500"; si tiene céntimos, completa."""
    text = money_str(value)
    return f"S/ {text[:-3]}" if text.endswith(".00") else f"S/ {text}"


def _clock(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    return f"{hour}:{dt.minute:02d} {'a. m.' if dt.hour < 12 else 'p. m.'}"


def _busiest_window(times: list[datetime]) -> tuple[datetime, datetime] | None:
    """Tramo de hasta 2 horas con más cobros (primer y último cobro de ese tramo)."""
    if len(times) < 2:
        return None
    ordered = sorted(times)
    best: tuple[int, int] = (0, 0)
    end = 0
    for start in range(len(ordered)):
        while end + 1 < len(ordered) and ordered[end + 1] - ordered[start] <= timedelta(hours=2):
            end += 1
        if end - start > best[1] - best[0]:
            best = (start, end)
    first, last = ordered[best[0]], ordered[best[1]]
    return (first, last) if first != last else None


def _moment(dt: datetime) -> str:
    if dt.hour < 12:
        return "En la mañanita"
    if dt.hour < 19:
        return "En la tarde"
    return "En la noche"


def build(db: Session, business: Business, wallet: Wallet) -> str:
    today = to_business(now_utc()).date()
    movements, _ = wallets_service.list_movements(db, business.id, wallet_id=wallet.id, limit=100)
    sales = [
        (to_business(datetime.fromisoformat(m["occurred_at"])), Decimal(m["amount"]))
        for m in movements
        if m["direction"] == "IN"
        and to_business(datetime.fromisoformat(m["occurred_at"])).date() == today
    ]
    total = sum((amount for _, amount in sales), Decimal("0"))
    count = len(sales)
    profile = db.get(AgentProfile, wallet.id)
    answers = profile.answers if profile else []
    goal = declared_daily_sales(answers[2]) if len(answers) > 2 else None
    top = answers[1].strip() if len(answers) > 1 and answers[1].strip() else None

    if count == 0:
        return (
            f"Aún no recibes yapeos hoy en tu **{wallet.name}**. "
            "Apenas entre el primero, aquí te muestro cómo va tu día. 💪"
        )

    ratio = total / goal if goal else None
    if ratio is not None and ratio >= 1:
        head = f"🎉 ¡Qué buen día! Ya pasaste tu meta en tu **{wallet.name}**."
    elif ratio is not None and ratio >= Decimal("0.8"):
        head = f"🎉 ¡Qué buen día! Hoy te fue súper bien en tu **{wallet.name}**."
    else:
        head = f"👏 ¡Vas avanzando! Así va tu día en tu **{wallet.name}**."

    average = total / count
    total_line = f"💰 **Total cobrado hoy:** **{_soles(total)}**"
    if goal and Decimal("0.9") * goal <= total < goal:
        total_line += f" (¡Casi {_goal(goal)}!)"
    lines = [
        total_line,
        f"📱 Recibiste **{count} {'yapeo' if count == 1 else 'yapeos'}** en total "
        f"(promedio de {_soles(average)} por cliente).",
    ]
    if goal:
        missing = goal - total
        if missing > 0:
            push = " ¡Un yapeito más y lo logras! 🚀" if missing <= average else " ¡Tú puedes! 🚀"
            lines.append(
                f"🎯 **Tu meta del día:** te faltan solo **{_soles(missing)}** para llegar a los "
                f"{_goal(goal)}.{push}"
            )
        else:
            lines.append(
                f"🎯 **Tu meta del día:** ¡la superaste por **{_soles(-missing)}**! "
                f"Tu meta era {_goal(goal)}. 🚀"
            )
    else:
        lines.append(
            "🎯 **Tu meta del día:** cuéntame cuánto vendes en un día normal y te digo "
            "cuánto te falta."
        )
    window = _busiest_window([when for when, _ in sales])
    if window:
        first, last = window
        span = (
            f"alrededor de las {_clock(first)}"
            if last - first < timedelta(minutes=10)
            else f"entre las {_clock(first)} y las {_clock(last)}"
        )
        lines.append(f"⏰ **Tu hora más movida:** {_moment(first)}, {span}")
    if top:
        lines.append(f"🛍️ **Lo que más vendes:** {top} (según me contaste).")
    card = "\n>\n".join(f"> {line}" for line in lines)
    return f"{head}\n\n{card}"
