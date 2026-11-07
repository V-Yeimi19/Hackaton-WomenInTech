"""Escenarios sintéticos aislados para la demostración.

Los datos son ficticios y viven solo en ``DEMO``. No se mezclan con personas
reales ni con un entorno ``LIVE``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import encrypt_phone, normalize_phone, phone_lookup_hash
from app.db.base import utcnow
from app.modules.business.models import Business
from app.modules.consents import service as consents_service
from app.modules.consents.models import Preference
from app.modules.identity.models import ChannelLink, User
from app.modules.insights import service as insights_service
from app.modules.insights.models import WeeklyFact
from app.modules.ledger import domain as ledger_domain
from app.modules.ledger import service as ledger_service
from app.shared.clock import week_start

settings = get_settings()
WEEK = timedelta(days=7)
DEFAULT_DEMO_PHONE = "+51999999999"


def _create_business(db: Session, user: User, *, name: str, category: str) -> Business:
    business = Business(
        owner_id=user.id,
        name=name,
        category=category,
        status="ACTIVE",
        timezone=settings.app_timezone,
        currency="PEN",
        environment="DEMO",
        demo_debt_status="UNKNOWN",
        demo_credit_active=False,
    )
    db.add(business)
    db.flush()

    ledger_service.ensure_accounts(db, business.id)
    db.add(
        Preference(
            business_id=business.id,
            reports_enabled=True,
            format="TEXT",
            schedule_local=settings.weekly_report_local_time,
            invitations_enabled=True,
        )
    )
    consents_service.grant(
        db, business.id, "CORE_PROCESSING", policy_version=settings.rules_version, commit=False
    )
    consents_service.grant(
        db, business.id, "WHATSAPP_REPORTS", policy_version=settings.rules_version, commit=False
    )
    consents_service.grant(
        db, business.id, "PRODUCT_INVITATIONS", policy_version=settings.rules_version, commit=False
    )
    return business


def _link_phone(db: Session, business: Business, phone: str | None) -> ChannelLink:
    # Los escenarios nunca verifican un teléfono real ni reasignan vínculos.
    # En Twilio se requiere VINCULAR desde el propio teléfono.
    if settings.messaging_mode == "twilio":
        raise ValueError("El vínculo real requiere un código de un solo uso")
    normalized = normalize_phone(phone or ("+519" + str(business.id.int % 100000000).zfill(8)))
    lookup = phone_lookup_hash(normalized)
    existing = db.scalar(select(ChannelLink).where(ChannelLink.phone_lookup_hash == lookup))
    if existing is not None:
        if existing.business_id != business.id:
            raise ValueError("El teléfono ya pertenece a otro escenario")
        return existing
    link = ChannelLink(
        business_id=business.id,
        provider="twilio",
        environment="DEMO",
        phone_encrypted=encrypt_phone(normalized),
        phone_lookup_hash=lookup,
        verified_at=utcnow(),
        status="ACTIVE",
        last_inbound_at=utcnow(),
    )
    db.add(link)
    db.flush()
    return link


def _spread_times(now: datetime, count: int) -> list[datetime]:
    start = week_start(now)
    base = max(start, now - timedelta(minutes=count))
    span = now - base
    if count <= 1 or span.total_seconds() <= 0:
        return [now for _ in range(count)]
    return sorted(base + span * (index + 1) / (count + 1) for index in range(count))


def _post(
    db: Session,
    business: Business,
    kind: str,
    amount: str,
    occurred_at: datetime,
    *,
    medium: str = ledger_domain.DIGITAL,
    target_account_kind: str | None = None,
):
    return ledger_service.post(
        db,
        business_id=business.id,
        kind=kind,
        amount=Decimal(amount),
        medium=medium,
        source=ledger_domain.SIMULATED,
        environment="DEMO",
        occurred_at=occurred_at,
        classification_source=ledger_domain.EXPLICIT_ACTION,
        target_account_kind=target_account_kind,
        commit=False,
    )


def _seed_previous_facts(
    db: Session,
    business: Business,
    now: datetime,
    *,
    sales: str,
    payments: str,
    withdrawals: str,
    contributions: str,
    stable: bool,
    weeks: int = 4,
) -> None:
    start_of_week = week_start(now)
    sales_d = Decimal(sales)
    payments_d = Decimal(payments)
    withdrawals_d = Decimal(withdrawals)
    contributions_d = Decimal(contributions)
    for index in range(1, weeks + 1):
        week = start_of_week - timedelta(weeks=index)
        db.add(
            WeeklyFact(
                business_id=business.id,
                week_start=week,
                revision=1,
                sales=sales_d,
                payments=payments_d,
                withdrawals=withdrawals_d,
                contributions=contributions_d,
                operating_flow=(sales_d - payments_d).quantize(Decimal("0.01")),
                coverage_status="RECORDED_ONLY",
                stable=stable,
                rules_version=settings.rules_version,
                data_cutoff_at=week + WEEK,
            )
        )
    db.flush()


def _seed_risk(db: Session, user: User, phone: str | None) -> Business:
    now = utcnow()
    business = _create_business(db, user, name="Bodega Rosa", category="Bodega")
    business.demo_debt_status = "KNOWN_DEBT"
    business.demo_credit_active = False

    # Escenario 3.7: apertura de hogar S/300, ventas S/1 500, pago S/800,
    # aporte S/300 y retiro S/600.
    times = _spread_times(now, 6)
    _post(
        db,
        business,
        ledger_domain.OPENING_BALANCE,
        "300.00",
        times[0],
        target_account_kind=ledger_domain.HOUSEHOLD_DIGITAL,
    )
    _post(db, business, ledger_domain.SALE, "1200.00", times[1])
    _post(
        db,
        business,
        ledger_domain.SALE,
        "300.00",
        times[2],
        medium=ledger_domain.CASH,
    )
    _post(db, business, ledger_domain.BUSINESS_PAYMENT, "800.00", times[3])
    _post(db, business, ledger_domain.OWNER_CONTRIBUTION, "300.00", times[4])
    _post(db, business, ledger_domain.HOUSEHOLD_WITHDRAWAL, "600.00", times[5])

    _seed_previous_facts(
        db,
        business,
        now,
        sales="1500.00",
        payments="800.00",
        withdrawals="600.00",
        contributions="300.00",
        stable=True,
        weeks=4,
    )

    # Compromiso digital que dispara PAYMENT_SHORTFALL (faltante S/1 400).
    from app.modules.commitments.models import Commitment

    digital = ledger_service.get_account(db, business.id, ledger_domain.BUSINESS_DIGITAL)
    db.add(
        Commitment(
            business_id=business.id,
            label="Proveedor mayorista",
            amount=Decimal("1500.00"),
            payment_account_id=digital.id,
            due_at=now + timedelta(days=2),
            source="SIMULATED",
            confirmed_at=now,
            status="OPEN",
        )
    )
    db.flush()

    if settings.messaging_mode != "twilio":
        _link_phone(db, business, phone)
    db.flush()
    insights_service.generate_report(db, business, cutoff_at=now, kind="PRELIMINARY", commit=False)
    db.commit()
    db.refresh(business)
    return business


def _seed_stable(db: Session, user: User, phone: str | None) -> Business:
    now = utcnow()
    business = _create_business(db, user, name="Bodega Estable", category="Abarrotes")
    business.demo_debt_status = "NONE"
    business.demo_credit_active = False

    current_start = week_start(now)
    for index in range(8, 0, -1):
        week = current_start - timedelta(weeks=index)
        _post(db, business, ledger_domain.SALE, "1000.00", week + timedelta(days=1))
        _post(
            db,
            business,
            ledger_domain.BUSINESS_PAYMENT,
            "400.00",
            week + timedelta(days=2),
        )
        _post(
            db,
            business,
            ledger_domain.HOUSEHOLD_WITHDRAWAL,
            "200.00",
            week + timedelta(days=3),
        )
        db.add(
            WeeklyFact(
                business_id=business.id,
                week_start=week,
                revision=1,
                sales=Decimal("1000.00"),
                payments=Decimal("400.00"),
                withdrawals=Decimal("200.00"),
                contributions=Decimal("0.00"),
                operating_flow=Decimal("600.00"),
                coverage_status="RECORDED_ONLY",
                stable=True,
                rules_version=settings.rules_version,
                data_cutoff_at=week + WEEK,
            )
        )
    db.flush()

    if settings.messaging_mode != "twilio":
        _link_phone(db, business, phone)
    db.flush()

    # Reporte final de la última semana completa con oportunidad elegible.
    cutoff = current_start + timedelta(minutes=1)
    insights_service.generate_report(
        db, business, cutoff_at=cutoff, kind="WEEKLY_FINAL", commit=False
    )
    db.commit()
    db.refresh(business)
    return business


def seed_scenario(
    db: Session,
    user: User,
    scenario: str,
    *,
    phone: str | None = None,
) -> Business | None:
    if scenario == "empty":
        return None
    if scenario == "risk":
        return _seed_risk(db, user, phone)
    if scenario == "stable":
        return _seed_stable(db, user, phone)
    return None


def reset_business(db: Session, business_id: uuid.UUID) -> None:
    """Reservado para demos. En P0 no se borran asientos confirmados."""
    raise NotImplementedError("El reset debe implementarse como nuevo escenario aislado.")


__all__ = ["seed_scenario", "DEFAULT_DEMO_PHONE"]
