"""Día de la semana del reporte semanal por negocio (lunes = 0 … domingo = 6)."""

import sqlalchemy as sa
from alembic import op

revision = "0011_report_schedule_weekday"
down_revision = "0010_telegram_dashboard"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE preferences ADD COLUMN IF NOT EXISTS schedule_weekday smallint "
        "NOT NULL DEFAULT 6"
    )
    op.execute(
        "DO $$ BEGIN "
        "ALTER TABLE preferences ADD CONSTRAINT ck_preferences_schedule_weekday "
        "CHECK (schedule_weekday BETWEEN 0 AND 6); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    _backfill_from_profiles()


def _backfill_from_profiles():
    """Aplica los horarios que las usuarias ya le dieron a Mica (pregunta 5 del perfil)."""
    from app.modules.agent.schedule import parse_schedule

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT business_id, answers->>4 AS answer FROM agent_profiles "
            "WHERE jsonb_array_length(answers) > 4 ORDER BY updated_at"
        )
    ).all()
    # El perfil más reciente de cada negocio gana (orden ascendente, se sobrescribe).
    latest = {}
    for business_id, answer in rows:
        parsed = parse_schedule(answer or "")
        if parsed is not None:
            latest[business_id] = parsed
    for business_id, (weekday, hhmm) in latest.items():
        bind.execute(
            sa.text(
                "INSERT INTO preferences (business_id, reports_enabled, format, schedule_local, "
                "schedule_weekday, invitations_enabled, updated_at) "
                "VALUES (:b, true, 'TEXT', :t, :d, false, now()) "
                "ON CONFLICT (business_id) DO UPDATE SET schedule_local = :t, "
                "schedule_weekday = :d, updated_at = now()"
            ),
            {"b": business_id, "t": hhmm, "d": weekday},
        )


def downgrade():
    op.execute("ALTER TABLE preferences DROP CONSTRAINT IF EXISTS ck_preferences_schedule_weekday")
    op.execute("ALTER TABLE preferences DROP COLUMN IF EXISTS schedule_weekday")
