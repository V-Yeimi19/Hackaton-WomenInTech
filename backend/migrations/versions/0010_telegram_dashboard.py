"""Dashboards PDF solicitados por Telegram y documento durable en outbox."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_telegram_dashboard"
down_revision = "0009_cash_confirmations"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE outbound_messages ADD COLUMN IF NOT EXISTS document jsonb")
    op.create_table(
        "telegram_dashboard_requests",
        sa.Column(
            "channel_link_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channel_links.id"),
            primary_key=True,
        ),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id"),
            nullable=False,
        ),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )
    op.create_index(
        "ix_telegram_dashboard_requests_business_id",
        "telegram_dashboard_requests",
        ["business_id"],
        if_not_exists=True,
    )


def downgrade():
    op.drop_table("telegram_dashboard_requests")
    op.drop_column("outbound_messages", "document")
