"""Recuperación, calendario e invariantes exigidas por el README."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.rate_limit import enforce
from app.db.base import utcnow
from app.jobs.scheduler import enqueue_weekly_reports
from app.jobs.service import run_due_jobs
from app.modules.consents import service as consents
from app.modules.identity.models import ChannelLink
from app.modules.insights import service as insights
from app.modules.ledger import domain as d
from app.modules.ledger.models import LedgerEntry
from app.modules.messaging import service as messaging
from app.shared.clock import week_start
from tests.integration.test_acceptance import post

pytestmark = pytest.mark.integration


def test_ca19_revoke_cancels_queued_report(db, business, message):
    consents.grant(db, business.id, "WHATSAPP_REPORTS")
    report = insights.generate_report(db, business, kind="PRELIMINARY")
    message.report_id = report.id
    db.commit()
    consents.revoke(db, business.id, "WHATSAPP_REPORTS")
    assert message.status == "CANCELLED"
    messaging.deliver_message(db, message)
    assert message.status == "CANCELLED"


def test_ca21_recover_persisted_inbox(db, business):
    payload = {
        "event_type": "transaction.confirmed",
        "business_reference": str(business.id),
        "amount": "120",
        "external_transaction_id": uuid.uuid4().hex,
        "kind": "SALE",
    }
    event, _ = messaging.persist_inbound(
        db,
        provider="simulator",
        event_id=uuid.uuid4().hex,
        business_id=business.id,
        payload=payload,
    )
    db.expire_all()
    messaging.process_pending_inbound(db, limit=1000)
    assert event.status == "DONE"
    messaging.process_inbound(db, event)
    from app.modules.ledger.service import balances

    assert balances(db, business.id)["business_digital"] == "120.00"


def test_ca14_preliminary_excludes_late_sunday_sale(db, business):
    from app.modules.ledger.service import post as ledger_post

    sunday = week_start(utcnow()) + timedelta(days=6, hours=20)
    ledger_post(
        db,
        business_id=business.id,
        kind=d.SALE,
        amount=Decimal("10"),
        source=d.SIMULATED,
        occurred_at=sunday + timedelta(hours=1),
    )
    preliminary = insights.compute_metrics(
        db, business.id, week_start(sunday), week_start(sunday) + timedelta(days=7), cutoff=sunday
    )
    final = insights.compute_metrics(
        db, business.id, week_start(sunday), week_start(sunday) + timedelta(days=7)
    )
    assert preliminary.sales == 0
    assert final.sales == 10


def test_late_event_creates_revision_without_overwriting(db, business):
    from app.modules.ledger.service import post as ledger_post

    period = week_start(utcnow()) - timedelta(days=7)
    cutoff = period + timedelta(days=7, minutes=5)
    report = insights.generate_report(db, business, cutoff_at=cutoff, kind="WEEKLY_FINAL")
    original_snapshot = dict(report.metrics_json)
    ledger_post(
        db,
        business_id=business.id,
        kind=d.SALE,
        amount=Decimal("50"),
        source=d.SIMULATED,
        occurred_at=period + timedelta(days=1),
    )
    run_due_jobs(db, limit=1000)
    latest = insights.latest_report(db, business.id, period_start=period)
    assert latest.revision > report.revision
    assert latest.metrics_json["sales_collected"] == "50.00"
    db.refresh(report)
    assert report.metrics_json == original_snapshot


def test_scheduler_sunday_and_monday_without_second_message(db, business):
    current = week_start(utcnow())
    business.created_at = current - timedelta(days=8)
    db.commit()
    sunday = current + timedelta(days=6, hours=20)
    enqueue_weekly_reports(db, now=sunday)
    from app.jobs.models import ScheduledJob

    jobs = list(db.scalars(select(ScheduledJob).where(ScheduledJob.business_id == business.id)))
    assert [j.payload_json["kind"] for j in jobs] == ["PRELIMINARY"]
    enqueue_weekly_reports(db, now=sunday)
    assert (
        len(list(db.scalars(select(ScheduledJob).where(ScheduledJob.business_id == business.id))))
        == 1
    )
    enqueue_weekly_reports(db, now=current + timedelta(days=7, minutes=5))
    assert (
        len(list(db.scalars(select(ScheduledJob).where(ScheduledJob.business_id == business.id))))
        == 2
    )


def test_entries_cannot_be_edited(db, business):
    post(db, business, d.SALE, "100")
    entry = db.scalars(select(LedgerEntry).where(LedgerEntry.business_id == business.id)).first()
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE ledger_entries SET delta = 999 WHERE id = :id"), {"id": entry.id})
        db.commit()
    db.rollback()


def test_channel_link_lookup_is_scoped_to_business(db, business):
    from app.core.security import encrypt_phone, phone_lookup_hash
    from app.modules.identity.models import ChannelLink
    from app.modules.identity.service import find_link_by_phone

    phone = "+51900001234"
    db.add(
        ChannelLink(
            business_id=business.id,
            environment="DEMO",
            phone_encrypted=encrypt_phone(phone),
            phone_lookup_hash=phone_lookup_hash(phone),
            status="ACTIVE",
        )
    )
    db.commit()

    assert find_link_by_phone(db, phone, business_id=business.id) is not None
    assert find_link_by_phone(db, phone, business_id=uuid.uuid4()) is None


def test_cross_business_reference_rejected(db, business, message):
    link = db.get(ChannelLink, message.channel_link_id)
    with pytest.raises(IntegrityError):
        db.execute(
            text("UPDATE outbound_messages SET business_id = :id WHERE id = :message"),
            {"id": uuid.uuid4(), "message": message.id},
        )
        db.commit()
    db.rollback()
    assert link.business_id == business.id


def test_distributed_quota(db):
    from app.core.errors import AppError

    subject = uuid.uuid4().hex
    enforce(db, subject, "test", 1)
    with pytest.raises(AppError, match="Demasiadas"):
        enforce(db, subject, "test", 1)


def test_confirmed_transaction_amount_is_immutable(db, business):
    transaction = post(db, business, d.SALE, "100")
    with pytest.raises(IntegrityError):
        db.execute(
            text("UPDATE transactions SET amount = 200 WHERE id = :id"), {"id": transaction.id}
        )
        db.commit()
    db.rollback()


def test_entries_cannot_be_added_to_previous_transaction(db, business):
    transaction = post(db, business, d.SALE, "100")
    entry = db.scalars(
        select(LedgerEntry).where(LedgerEntry.transaction_id == transaction.id)
    ).first()
    db.add(
        LedgerEntry(
            business_id=business.id,
            transaction_id=transaction.id,
            account_id=entry.account_id,
            delta=Decimal("1"),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
