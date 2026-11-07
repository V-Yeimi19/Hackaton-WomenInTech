"""Esquema inicial P0 de Mica.

La migración crea las tablas declarativas y luego añade las invariantes que un
CHECK de fila no puede expresar: asientos balanceados por operación y toda
operación POSTED con asientos. Ambas validaciones son triggers diferidos al
commit, tal como pide el README.
"""

from __future__ import annotations

from alembic import op

from app.db.base import Base, load_models

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


BALANCED_FUNCTION = """
CREATE OR REPLACE FUNCTION mica_assert_balanced_transaction() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_transaction uuid;
    v_total numeric(14,2);
    v_status varchar(20);
BEGIN
    v_transaction := COALESCE(NEW.transaction_id, OLD.transaction_id);
    SELECT COALESCE(SUM(delta), 0)
      INTO v_total
      FROM ledger_entries
     WHERE transaction_id = v_transaction;
    SELECT status INTO v_status FROM transactions WHERE id = v_transaction;
    IF v_status = 'POSTED' AND v_total <> 0 THEN
        RAISE EXCEPTION 'Asientos desbalanceados para la operación %', v_transaction
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END;
$$;
"""

POSTED_FUNCTION = """
CREATE OR REPLACE FUNCTION mica_assert_posted_has_entries() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_count integer;
    v_total numeric(14,2);
BEGIN
    IF NEW.status = 'POSTED' THEN
        SELECT COUNT(*), COALESCE(SUM(delta), 0)
          INTO v_count, v_total
          FROM ledger_entries
         WHERE transaction_id = NEW.id;
        IF v_count = 0 THEN
            RAISE EXCEPTION 'La operación POSTED % no tiene asientos', NEW.id
                USING ERRCODE = '23514';
        END IF;
        IF v_total <> 0 THEN
            RAISE EXCEPTION 'La operación POSTED % está desbalanceada', NEW.id
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NULL;
END;
$$;
"""

BALANCED_TRIGGER = """
CREATE CONSTRAINT TRIGGER trg_ledger_entries_balanced
AFTER INSERT OR UPDATE OR DELETE ON ledger_entries
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION mica_assert_balanced_transaction();
"""

POSTED_TRIGGER = """
CREATE CONSTRAINT TRIGGER trg_transactions_posted_has_entries
AFTER INSERT OR UPDATE OF status ON transactions
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION mica_assert_posted_has_entries();
"""


def upgrade() -> None:
    load_models()
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.execute(BALANCED_FUNCTION)
    op.execute(POSTED_FUNCTION)
    op.execute(BALANCED_TRIGGER)
    op.execute(POSTED_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_transactions_posted_has_entries ON transactions;")
    op.execute("DROP TRIGGER IF EXISTS trg_ledger_entries_balanced ON ledger_entries;")
    op.execute("DROP FUNCTION IF EXISTS mica_assert_posted_has_entries();")
    op.execute("DROP FUNCTION IF EXISTS mica_assert_balanced_transaction();")
    load_models()
    Base.metadata.drop_all(bind=op.get_bind())
