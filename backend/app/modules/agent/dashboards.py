"""Resumen visual de negocio solicitado en Telegram, sin publicar movimientos."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.modules.agent.dashboard_periods import period
from app.modules.agent.declarations import is_report, normalized
from app.modules.agent.models import MoneyDeclaration
from app.modules.business.models import Business
from app.modules.identity.models import ChannelLink
from app.modules.ledger.models import LedgerEntry, Transaction
from app.modules.messaging.models import DashboardRequest
from app.modules.wallets import service as wallets
from app.modules.wallets.models import Wallet
from app.shared.clock import business_tz, to_business
from app.shared.money import money_str


@dataclass
class DashboardReply:
    text: str
    document: dict | None = None


def requested(text: str) -> bool:
    text = normalized(text)
    return any(
        word in text
        for word in ("pdf", "dashboard", "reporte visual", "reporte grafico", "resumen grafico")
    )


def snapshot(
    db: Session, business: Business, selected: list[Wallet], start: date, end: date
) -> dict:
    """Libro como fuente principal. Digital declarado solo cubre días sin registros.

    Efectivo confirmado ya está en el libro. No se suma de nuevo la declaración.
    Digital: por billetera/día/dirección, el libro sustituye cualquier declaración;
    sin libro usamos la última declaración confirmada de ese día, nunca la suma
    de sucesivas declaraciones del mismo total diario.
    """
    lower = datetime.combine(start, time.min, tzinfo=business_tz())
    upper = datetime.combine(end + timedelta(days=1), time.min, tzinfo=business_tz())
    accounts = {
        account: w
        for w in selected
        for account in (w.account_id, w.cash_account_id)
        if account is not None
    }
    rows = db.execute(
        select(Transaction, LedgerEntry.account_id, LedgerEntry.delta)
        .join(LedgerEntry, LedgerEntry.transaction_id == Transaction.id)
        .where(
            Transaction.business_id == business.id,
            LedgerEntry.business_id == business.id,
            LedgerEntry.account_id.in_(accounts),
            Transaction.status == "POSTED",
            Transaction.occurred_at >= lower,
            Transaction.occurred_at < upper,
        )
    ).all()
    # Los asientos de reversión y reclasificación conservan su signo, y se
    # atribuyen al tipo económico original, sin contar traslados ni aperturas.
    parent_ids = {tx.reversal_of or tx.adjustment_of for tx, _, _ in rows} - {None}
    parents = {
        tx.id: tx
        for tx in db.scalars(
            select(Transaction).where(
                Transaction.id.in_(parent_ids), Transaction.business_id == business.id
            )
        )
    }
    totals: dict[tuple[str, str, str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    ledger_keys = set()
    for tx, account_id, delta in rows:
        economic = parents.get(tx.reversal_of or tx.adjustment_of, tx)
        if economic.kind not in ("SALE", "BUSINESS_PAYMENT", "PERSONAL_INCOME", "PERSONAL_PAYMENT"):
            continue
        direction = "IN" if economic.kind in ("SALE", "PERSONAL_INCOME") else "OUT"
        day = str(to_business(tx.occurred_at).date())
        key = (str(accounts[account_id].id), day, direction, tx.medium)
        totals[key] += Decimal(delta) * (1 if direction == "IN" else -1)
        ledger_keys.add(key)
    selected_ids = {str(w.id) for w in selected}
    declarations = db.scalars(
        select(MoneyDeclaration)
        .where(MoneyDeclaration.business_id == business.id, MoneyDeclaration.status == "CONFIRMED")
        .order_by(MoneyDeclaration.confirmed_at.desc(), MoneyDeclaration.id.desc())
    )
    declared_keys = set()
    declared_by_wallet: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for declaration in declarations:
        daily: dict[tuple[str, str, str, str], Decimal] = defaultdict(lambda: Decimal("0"))
        for entry in declaration.data.get("entries", []):
            if (
                entry["wallet_id"] not in selected_ids
                or entry["medium"] != "DIGITAL"
                or not str(start) <= entry["day"] <= str(end)
            ):
                continue
            key = (entry["wallet_id"], entry["day"], entry["direction"], "DIGITAL")
            daily[key] += Decimal(entry["amount"])
        for key, value in daily.items():
            if key in ledger_keys or key in declared_keys:
                continue
            totals[key] = value
            declared_by_wallet[key[0]] += value
            declared_keys.add(key)

    def summarize(scope: list[Wallet]) -> dict:
        scope_ids = {str(w.id) for w in scope}
        scoped = {key: amount for key, amount in totals.items() if key[0] in scope_ids}
        days: dict[str, dict[str, Decimal]] = {}
        current = start
        while current <= end:
            days[str(current)] = {"IN": Decimal("0"), "OUT": Decimal("0")}
            current += timedelta(days=1)
        media = {
            "CASH": {"IN": Decimal("0"), "OUT": Decimal("0")},
            "DIGITAL": {"IN": Decimal("0"), "OUT": Decimal("0")},
        }
        for (_, day, direction, medium), amount in scoped.items():
            days[day][direction] += amount
            media[medium][direction] += amount
        incoming = sum((d["IN"] for d in days.values()), Decimal("0"))
        outgoing = sum((d["OUT"] for d in days.values()), Decimal("0"))
        return {
            "version": 1,
            "wallet_names": [w.name for w in scope],
            "start": str(start),
            "end": str(end),
            "generated_at": utcnow().isoformat(),
            "income": money_str(incoming),
            "expense": money_str(outgoing),
            "net": money_str(incoming - outgoing),
            "days": [
                {"day": day, "income": money_str(values["IN"]), "expense": money_str(values["OUT"])}
                for day, values in days.items()
            ],
            "media": {
                m: {"income": money_str(v["IN"]), "expense": money_str(v["OUT"])}
                for m, v in media.items()
            },
            "declared_digital": money_str(
                sum((declared_by_wallet[str(w.id)] for w in scope), Decimal("0"))
            ),
            "empty": not scoped,
            "environment": business.environment,
            "includes_personal": any(w.purpose == "PERSONAL" for w in scope),
        }

    document = summarize(selected)
    if len(selected) > 1:
        document["section_title"] = "Resumen general"
        document["wallet_reports"] = [
            {
                **summarize([wallet]),
                "wallet_id": str(wallet.id),
                "section_title": "Resumen de billetera",
            }
            for wallet in selected
        ]
    return document


def handle(
    db: Session, business: Business, link: ChannelLink, text: str, when: datetime
) -> DashboardReply | None:
    if link.provider != "telegram":
        return None
    db.scalar(select(Business).where(Business.id == business.id).with_for_update())
    explicit = requested(text)
    pending = db.get(DashboardRequest, link.id)
    if pending and (pending.business_id != business.id or pending.expires_at <= utcnow()):
        db.delete(pending)
        db.flush()
        pending = None
    if not explicit and (
        not pending
        or is_report(text)
        or normalized(text) in ("confirmar", "editar", "ayuda", "resumen", "pausar", "reanudar")
    ):
        return None
    if business.status != "ACTIVE":
        return DashboardReply("Tu negocio no está activo. No puedo preparar su PDF.")
    if normalized(text) == "cancelar":
        if pending:
            db.delete(pending)
        return DashboardReply("Cancelé el PDF. Tus movimientos siguen guardados.")
    data = dict(pending.data) if pending and not explicit else {}
    active = wallets.active_wallets(db, business.id)
    available = [w for w in active if wallets.is_business_wallet(w)]
    word = normalized(text)
    all_wallets = bool(
        re.search(r"\b(?:todas|todos)(?:\s+(?:mis|las|los|sus))*\s+(?:billeteras|cuentas)\b", word)
    ) and not re.search(r"\b(?:billeteras|cuentas)\s+(?:personales|de\s+(?:mi\s+)?negocio)\b", word)
    if all_wallets:
        data.update(
            wallet_ids=[str(w.id) for w in active], include_personal=False, personal_only=False
        )
    elif "personal" in word or "principal" in word:
        data["include_personal"] = True
        data["personal_only"] = "negocio" not in word and not any(
            normalized(w.name) in word for w in available
        )
    if not available and not data.get("include_personal") and not data.get("wallet_ids"):
        return DashboardReply("Necesitas una billetera de negocio para pedir este PDF.")
    chosen = [w for w in active if normalized(w.name) in word]
    if all_wallets:
        pass
    elif "todos mis negocios" in word or "todos los negocios" in word:
        data["wallet_ids"] = [str(w.id) for w in available]
    elif chosen:
        data["wallet_ids"] = [str(w.id) for w in chosen]
    elif len(available) == 1 and not data.get("wallet_ids"):
        data["wallet_ids"] = [str(available[0].id)]
    try:
        dates = period(text, to_business(when).date())
    except ValueError as exc:
        error = str(exc)
        dates = None
        data.pop("start", None)
        data.pop("end", None)
    else:
        error = ""
    if dates:
        data.update(start=str(dates[0]), end=str(dates[1]))
    if pending is None:
        pending = DashboardRequest(channel_link_id=link.id, business_id=business.id, data={})
    pending.data = data
    pending.expires_at = utcnow() + timedelta(minutes=30)
    if "start" not in data:
        db.add(pending)
        return DashboardReply(
            (error + "\n" if error else "")
            + "¿De qué periodo quieres el PDF? Puedes decir hoy, esta semana, este mes o del 01/10/2026 al 31/10/2026. También puedes escribir Cancelar."
        )
    selected = [w for w in active if str(w.id) in data.get("wallet_ids", [])]
    if not selected and not data.get("personal_only"):
        db.add(pending)
        return DashboardReply(
            "¿De qué negocio quieres el PDF? Escribe su nombre: "
            + ", ".join(w.name for w in available)
            + ". También puedes pedir todos mis negocios."
        )
    if data.get("personal_only"):
        selected = []
    if data.get("include_personal"):
        selected.extend(w for w in active if w.role == "PRINCIPAL" and w not in selected)
    if not selected:
        return DashboardReply("No encontré una billetera activa para preparar ese PDF.")
    document = snapshot(
        db, business, selected, date.fromisoformat(data["start"]), date.fromisoformat(data["end"])
    )
    if pending in db:
        db.delete(pending)
    return DashboardReply(
        f"Tu resumen visual de {', '.join(w.name for w in selected)} · {data['start']} al {data['end']}.",
        document,
    )
