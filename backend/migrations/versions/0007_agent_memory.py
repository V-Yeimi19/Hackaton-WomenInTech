"""Memoria compartida de Mica e historial independiente de la app.

Revision ID: 0007_agent_memory
Revises: 0006_telegram_reply_markup
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_agent_memory"
down_revision = "0006_telegram_reply_markup"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_profiles",
        sa.Column(
            "wallet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallets.id"),
            primary_key=True,
        ),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id"),
            nullable=False,
        ),
        sa.Column("answers", postgresql.JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )
    op.create_index("ix_agent_profiles_business_id", "agent_profiles", ["business_id"], if_not_exists=True)
    op.create_table(
        "agent_app_exchanges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id"),
            nullable=False,
        ),
        sa.Column(
            "wallet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wallets.id"), nullable=False
        ),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("reply", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("wallet_id", "request_id", name="uq_agent_app_request"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_agent_app_history",
        "agent_app_exchanges",
        ["business_id", "wallet_id", "created_at", "id"],
        if_not_exists=True,
    )


def downgrade():
    op.drop_table("agent_app_exchanges")
    op.drop_table("agent_profiles")
