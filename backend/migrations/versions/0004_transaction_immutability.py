"""Proteger operaciones confirmadas y evitar asientos añadidos posteriormente."""

from alembic import op

revision = "0004_transaction_immutability"
down_revision = "0003_quotas"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE FUNCTION mica_protect_transaction() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'No se borran operaciones' USING ERRCODE = '23514';
      END IF;
      IF OLD.status = 'POSTED' THEN
        IF (to_jsonb(OLD) - ARRAY['kind','classification_source','replacement_for'])
           IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['kind','classification_source','replacement_for']) THEN
          RAISE EXCEPTION 'Operación confirmada inmutable' USING ERRCODE = '23514';
        END IF;
        IF (OLD.kind, OLD.classification_source) IS DISTINCT FROM (NEW.kind, NEW.classification_source)
           AND NOT (OLD.kind = 'UNKNOWN_OUTFLOW'
                    AND NEW.kind IN ('BUSINESS_PAYMENT', 'HOUSEHOLD_WITHDRAWAL')
                    AND NEW.classification_source = 'USER_CONFIRMED') THEN
          RAISE EXCEPTION 'Reclasificación no permitida' USING ERRCODE = '23514';
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$;
    CREATE TRIGGER trg_transactions_immutable BEFORE UPDATE OR DELETE ON transactions
    FOR EACH ROW EXECUTE FUNCTION mica_protect_transaction();
    """)
    op.execute("""
    CREATE FUNCTION mica_protect_new_entry() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE created_in_transaction boolean;
    BEGIN
      SELECT xmin = pg_current_xact_id()::text::xid INTO created_in_transaction
      FROM transactions WHERE id = NEW.transaction_id;
      IF created_in_transaction IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'No se añaden asientos a operaciones anteriores' USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END;
    $$;
    CREATE TRIGGER trg_entries_publication BEFORE INSERT ON ledger_entries
    FOR EACH ROW EXECUTE FUNCTION mica_protect_new_entry();
    """)


def downgrade():
    op.execute("DROP TRIGGER trg_entries_publication ON ledger_entries")
    op.execute("DROP FUNCTION mica_protect_new_entry()")
    op.execute("DROP TRIGGER trg_transactions_immutable ON transactions")
    op.execute("DROP FUNCTION mica_protect_transaction()")
