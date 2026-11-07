"""Aislamiento por negocio e inmutabilidad del libro y snapshots.

Revision ID: 0002_integrity
Revises: 0001_initial
"""

from alembic import op

revision = "0002_integrity"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

PARENTS = ("accounts", "transactions", "weekly_reports", "channel_links")
REFERENCES = (
    ("ledger_entries", "transaction_id", "transactions"),
    ("ledger_entries", "account_id", "accounts"),
    ("transactions", "reversal_of", "transactions"),
    ("transactions", "replacement_for", "transactions"),
    ("transactions", "adjustment_of", "transactions"),
    ("classification_requests", "transaction_id", "transactions"),
    ("commitments", "payment_account_id", "accounts"),
    ("commitments", "paid_transaction_id", "transactions"),
    ("alerts", "report_id", "weekly_reports"),
    ("opportunity_evaluations", "report_id", "weekly_reports"),
    ("outbound_messages", "report_id", "weekly_reports"),
    ("outbound_messages", "channel_link_id", "channel_links"),
)
IMMUTABLE = ("ledger_entries", "weekly_reports", "weekly_facts", "audit_events")


def upgrade():
    for table in PARENTS:
        op.create_unique_constraint(f"uq_{table}_business_id", table, ["business_id", "id"])
    for table, column, parent in REFERENCES:
        op.create_foreign_key(
            f"fk_{table}_{column}_business",
            table,
            parent,
            ["business_id", column],
            ["business_id", "id"],
        )
    op.execute("""
        CREATE FUNCTION mica_deny_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Registro inmutable: %', TG_TABLE_NAME USING ERRCODE = '23514';
        END;
        $$;
    """)
    for table in IMMUTABLE:
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION mica_deny_mutation()"
        )


def downgrade():
    for table in IMMUTABLE:
        op.execute(f"DROP TRIGGER trg_{table}_immutable ON {table}")
    op.execute("DROP FUNCTION mica_deny_mutation()")
    for table, column, _ in reversed(REFERENCES):
        op.drop_constraint(f"fk_{table}_{column}_business", table, type_="foreignkey")
    for table in PARENTS:
        op.drop_constraint(f"uq_{table}_business_id", table, type_="unique")
