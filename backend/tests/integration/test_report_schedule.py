"""El reporte semanal sale en el día y la hora que cada negocio le dio a Mica."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db.base import utcnow
from app.jobs.models import ScheduledJob
from app.jobs.scheduler import enqueue_weekly_reports
from app.modules.agent import schedule as report_schedule
from app.modules.agent.service import report_status
from app.modules.consents.models import Preference
from app.shared.clock import week_start

pytestmark = pytest.mark.integration


def _jobs(db, business):
    return list(db.scalars(select(ScheduledJob).where(ScheduledJob.business_id == business.id)))


def test_report_is_queued_at_the_chosen_day_and_time(db, business):
    current = week_start(utcnow())
    business.created_at = current - timedelta(days=8)
    report_schedule.save(db, business.id, 0, "14:10")  # lunes 2:10 p. m.
    db.commit()
    slot = current + timedelta(hours=14, minutes=10)

    # Antes de la hora (pasado el cierre del lunes 00:05) solo se consolida la semana anterior.
    enqueue_weekly_reports(db, now=slot - timedelta(minutes=1))
    assert [j.payload_json["kind"] for j in _jobs(db, business)] == ["WEEKLY_FINAL"]

    # A la hora elegida se encola el reporte que se envía: la semana anterior completa.
    enqueue_weekly_reports(db, now=slot)
    sent = [j for j in _jobs(db, business) if j.payload_json["kind"] == "PRELIMINARY"]
    assert len(sent) == 1
    assert sent[0].payload_json["cutoff_at"] == slot.isoformat()
    assert sent[0].payload_json["period_start"] == (current - timedelta(days=7)).isoformat()

    # Reintentos del planificador no lo duplican, y el domingo 20:00 ya no aplica.
    enqueue_weekly_reports(db, now=slot + timedelta(minutes=3))
    enqueue_weekly_reports(db, now=current + timedelta(days=6, hours=20))
    assert len([j for j in _jobs(db, business) if j.payload_json["kind"] == "PRELIMINARY"]) == 1


def test_late_week_schedule_reports_the_current_week(db, business):
    current = week_start(utcnow())
    business.created_at = current - timedelta(days=8)
    report_schedule.save(db, business.id, 4, "18:00")  # viernes 6 p. m.
    db.commit()
    slot = current + timedelta(days=4, hours=18)
    enqueue_weekly_reports(db, now=slot)
    sent = [j for j in _jobs(db, business) if j.payload_json["kind"] == "PRELIMINARY"]
    assert [j.payload_json["period_start"] for j in sent] == [current.isoformat()]


def test_chat_request_reschedules_and_mica_knows_it(db, business):
    assert report_schedule.request_change(db, business.id, "hola mica") is None
    assert report_schedule.request_change(db, business.id, "el viernes vendí 200") is None
    reply = report_schedule.request_change(
        db, business.id, "mándame el reporte los viernes a las 6pm"
    )
    assert reply is not None and "viernes a las 6:00 p. m." in reply
    db.commit()
    prefs = db.get(Preference, business.id)
    assert (prefs.schedule_weekday, prefs.schedule_local) == (4, "18:00")
    status = report_status(db, business.id)
    assert status["horario"] == "viernes a las 6:00 p. m."
    assert status["estado"].startswith("no se envía")  # sin Telegram vinculado


def test_conversation_asks_day_and_time_then_reschedules(db, business):
    from app.modules.agent.schedule import ASK

    told = "Tu reporte semanal está programado para enviarse cada lunes a las 2:10 p. m."
    # Preguntar si está programado no inicia un cambio.
    assert report_schedule.request_change(db, business.id, "¿está programado mi reporte?") is None
    # "¿Puedo cambiarlo?" después de hablar del reporte: Mica pregunta día y hora.
    ask = report_schedule.request_change(db, business.id, "puedo cambiarlo?", told)
    assert ask is not None and ASK in ask
    # Respuesta incompleta: vuelve a preguntar.
    again = report_schedule.request_change(db, business.id, "el jueves", ask)
    assert again is not None and again.startswith("Me falta")
    # Respuesta completa, sin repetir la palabra "reporte": se reprograma.
    done = report_schedule.request_change(db, business.id, "jueves a las 3pm", again)
    assert done is not None and "jueves a las 3:00 p. m." in done
    db.commit()
    prefs = db.get(Preference, business.id)
    assert (prefs.schedule_weekday, prefs.schedule_local) == (3, "15:00")
    # Fuera de esa conversación, un día y hora sueltos no cambian nada.
    assert (
        report_schedule.request_change(db, business.id, "el lunes a las 9am vendí 50", done) is None
    )
