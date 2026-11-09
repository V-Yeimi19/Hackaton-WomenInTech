"""Efectivo por billetera y declaraciones pendientes de confirmación.

Revision ID: 0009_cash_confirmations
Revises: 0008_telegram_audio
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_cash_confirmations"
down_revision = "0008_telegram_audio"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE wallets ADD COLUMN IF NOT EXISTS cash_account_id uuid")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_wallets_cash_account ON wallets(cash_account_id)"
    )
    op.execute("ALTER TABLE accounts DROP CONSTRAINT IF EXISTS ck_accounts_kind")
    op.execute(
        "ALTER TABLE accounts ADD CONSTRAINT ck_accounts_kind CHECK (kind IN ('BUSINESS_DIGITAL','HOUSEHOLD_DIGITAL','CASH_DECLARED','EXTERNAL_CLEARING','WALLET','WALLET_CASH'))"
    )
    op.execute("DROP INDEX IF EXISTS uq_accounts_business_kind_fixed")
    op.execute(
        "CREATE UNIQUE INDEX uq_accounts_business_kind_fixed ON accounts(business_id,kind) WHERE kind NOT IN ('WALLET','WALLET_CASH')"
    )
    op.execute("""DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_wallets_cash_business') THEN
            ALTER TABLE wallets ADD CONSTRAINT fk_wallets_cash_business
            FOREIGN KEY (cash_account_id,business_id) REFERENCES accounts(id,business_id);
        END IF;
    END $$""")
    op.execute("ALTER TABLE agent_app_exchanges ADD COLUMN IF NOT EXISTS declaration jsonb")
    op.execute("ALTER TABLE agent_app_exchanges ADD COLUMN IF NOT EXISTS request_hash varchar(64)")
    op.create_table(
        "agent_money_declarations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("channel_key", sa.String(80), nullable=False),
        sa.Column("source_id", sa.String(160), nullable=False, unique=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("openings", postgresql.JSONB(), nullable=False),
        sa.Column("balance_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('PENDING','EDITING','CONFIRMED','CANCELLED','EXPIRED')",
            name="ck_money_declaration_status",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_money_declarations_business",
        "agent_money_declarations",
        ["business_id", "created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "uq_money_declaration_pending",
        "agent_money_declarations",
        ["business_id", "channel", "channel_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING','EDITING')"),
        if_not_exists=True,
    )


def downgrade():
    # Un downgrade no puede borrar movimientos de efectivo ya confirmados.
    bind = op.get_bind()
    if bind.execute(
        sa.text("SELECT EXISTS(SELECT 1 FROM accounts WHERE kind='WALLET_CASH')")
    ).scalar():
        raise RuntimeError(
            "Hay efectivo por billetera. Conserva la migración o exporta y concilia esos datos antes de revertir."
        )
    op.drop_table("agent_money_declarations")
    op.execute("ALTER TABLE agent_app_exchanges DROP COLUMN IF EXISTS declaration")
    op.execute("ALTER TABLE agent_app_exchanges DROP COLUMN IF EXISTS request_hash")
    op.execute("ALTER TABLE wallets DROP CONSTRAINT IF EXISTS fk_wallets_cash_business")
    op.execute("DROP INDEX IF EXISTS uq_wallets_cash_account")
    op.execute("ALTER TABLE wallets DROP COLUMN IF EXISTS cash_account_id")
    op.execute("DROP INDEX IF EXISTS uq_accounts_business_kind_fixed")
    op.execute(
        "CREATE UNIQUE INDEX uq_accounts_business_kind_fixed ON accounts(business_id,kind) WHERE kind <> 'WALLET'"
    )
    op.execute("ALTER TABLE accounts DROP CONSTRAINT IF EXISTS ck_accounts_kind")
    op.execute(
        "ALTER TABLE accounts ADD CONSTRAINT ck_accounts_kind CHECK (kind IN ('BUSINESS_DIGITAL','HOUSEHOLD_DIGITAL','CASH_DECLARED','EXTERNAL_CLEARING','WALLET'))"
    )
