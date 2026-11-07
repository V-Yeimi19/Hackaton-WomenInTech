"""Cuotas distribuidas para demo, reportes y vinculación."""

import sqlalchemy as sa
from alembic import op

revision = "0003_quotas"
down_revision = "0002_integrity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "request_quotas",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window", sa.BigInteger(), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("request_quotas")
