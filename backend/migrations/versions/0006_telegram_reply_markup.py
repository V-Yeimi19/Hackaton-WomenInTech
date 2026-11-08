"""Botones inline de Telegram en la bandeja de salida.

El cuerpo sigue siendo el texto visible; `reply_markup` guarda el teclado
inline que Telegram debe mostrar junto al mensaje. Es nullable para no afectar
los mensajes de WhatsApp ni los envíos simulados existentes.

Revision ID: 0006_telegram_reply_markup
Revises: 0005_wallets_phone_login
"""

from alembic import op

revision = "0006_telegram_reply_markup"
down_revision = "0005_wallets_phone_login"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE outbound_messages ADD COLUMN IF NOT EXISTS reply_markup jsonb")


def downgrade():
    op.execute("ALTER TABLE outbound_messages DROP COLUMN IF EXISTS reply_markup")
