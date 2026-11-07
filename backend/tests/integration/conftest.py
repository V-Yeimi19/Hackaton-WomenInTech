"""Pruebas contra una BD PostgreSQL migrada, sin tocar tablas ajenas."""

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.modules.business.models import Business
from app.modules.identity.models import ChannelLink, User
from app.modules.ledger import service as ledger
from app.modules.messaging import service as messaging


@pytest.fixture
def pg_engine():
    url = os.getenv("MICA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Configura MICA_TEST_DATABASE_URL con PostgreSQL de pruebas migrado")
    engine = create_engine(url)
    assert engine.dialect.name == "postgresql"
    yield engine
    engine.dispose()


@pytest.fixture
def db(pg_engine):
    with Session(pg_engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def business(db):
    user = User(display_name="Prueba sintética")
    db.add(user)
    db.flush()
    business = Business(owner_id=user.id, name="Prueba", environment="DEMO")
    db.add(business)
    db.flush()
    ledger.ensure_accounts(db, business.id)
    db.commit()
    return business


@pytest.fixture
def message(db, business):
    from app.core.security import encrypt_phone

    link = ChannelLink(
        business_id=business.id,
        phone_encrypted=encrypt_phone("+51900000000"),
        phone_lookup_hash=uuid.uuid4().hex,
        status="ACTIVE",
        last_inbound_at=utcnow(),
    )
    db.add(link)
    db.flush()
    return messaging.enqueue_outbound(
        db,
        business_id=business.id,
        channel_link_id=link.id,
        body="Prueba",
        dedupe_key=uuid.uuid4().hex,
        commit=True,
    )
