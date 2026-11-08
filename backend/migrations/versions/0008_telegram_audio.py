"""Texto derivado del audio, separado del payload original del inbox.

Revision ID: 0008_telegram_audio
Revises: 0007_agent_memory
"""

from alembic import op

revision = "0008_telegram_audio"
down_revision = "0007_agent_memory"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE inbound_events ADD COLUMN IF NOT EXISTS transcript text")


def downgrade():
    op.execute("ALTER TABLE inbound_events DROP COLUMN IF EXISTS transcript")
