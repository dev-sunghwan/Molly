import config
from calendar_repository import CalendarRepository
from intent_models import (
    IntentAction,
    IntentResolution,
    IntentSource,
    ResolutionStatus,
    ScheduleIntent,
    TimeRange,
)
from molly_core import MollyCore
import state_store
import utils


def test_molly_core_executes_create_event(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")

    state_store.init_db()
    repo = CalendarRepository.from_config()
    core = MollyCore(repo)

    resolution = IntentResolution(
        status=ResolutionStatus.READY,
        intent=ScheduleIntent(
            action=IntentAction.CREATE_EVENT,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input="윤하 테니스 넣어줘",
            target_calendar="younha",
            title="Tennis",
            target_date=utils._today_local(),
            time_range=TimeRange(start="17:00", end="18:00"),
            metadata={"all_day": False},
        ),
    )

    message = core.execute_resolution(resolution, user_id=123)
    events = repo.list_events(utils._today_local())
    log_rows = state_store.list_execution_log(limit=1)

    assert "Added to YounHa" in message
    assert any(event["summary"] == "Tennis" for event in events)
    assert log_rows[0]["user_id"] == 123
    assert log_rows[0]["action"] == "create_event"
    assert log_rows[0]["metadata"]["actor_user_id"] == 123


def test_molly_core_executes_remaining_month_from_today(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    monkeypatch.setattr(
        utils,
        "_now_local",
        lambda: utils.TZ.localize(__import__("datetime").datetime(2026, 5, 22, 12, 0)),
    )

    state_store.init_db()
    repo = CalendarRepository.from_config()
    core = MollyCore(repo)

    service = repo.service
    today = utils._today_local()
    first_of_month = today.replace(day=1)
    repo.backend_module.add_event(service, {"calendar": "family", "title": "Past this month", "date": first_of_month, "start": "09:00", "end": "10:00"})
    repo.backend_module.add_event(service, {"calendar": "family", "title": "Earlier today", "date": today, "start": "00:01", "end": "00:02"})
    repo.backend_module.add_event(service, {"calendar": "family", "title": "Still coming", "date": today, "start": "23:58", "end": "23:59"})

    resolution = IntentResolution(
        status=ResolutionStatus.READY,
        intent=ScheduleIntent(
            action=IntentAction.VIEW_RANGE,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input="이번 달 남은 일정",
            metadata={"command": "month_remaining"},
        ),
    )

    message = core.execute_resolution(resolution, user_id=123)

    assert "Still coming" in message
    assert "Earlier today" not in message
    if first_of_month < today:
        assert "Past this month" not in message



def test_molly_core_executes_explicit_remaining_month_from_today(monkeypatch, tmp_path):
    from datetime import date, datetime

    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    monkeypatch.setattr(
        utils,
        "_now_local",
        lambda: utils.TZ.localize(datetime(2026, 7, 13, 12, 0)),
    )

    state_store.init_db()
    repo = CalendarRepository.from_config()
    core = MollyCore(repo)

    service = repo.service
    repo.backend_module.add_event(
        service,
        {"calendar": "family", "title": "Past July", "date": date(2026, 7, 5), "start": "09:00", "end": "10:00"},
    )
    repo.backend_module.add_event(
        service,
        {"calendar": "family", "title": "Future July", "date": date(2026, 7, 20), "start": "09:00", "end": "10:00"},
    )
    repo.backend_module.add_event(
        service,
        {"calendar": "family", "title": "August event", "date": date(2026, 8, 1), "start": "09:00", "end": "10:00"},
    )

    resolution = IntentResolution(
        status=ResolutionStatus.READY,
        intent=ScheduleIntent(
            action=IntentAction.VIEW_RANGE,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input="남은 7월 일정 알려줘",
            metadata={"command": "month_remaining:2026-07"},
        ),
    )

    message = core.execute_resolution(resolution, user_id=123)

    assert "July 2026" in message
    assert "Future July" in message
    assert "Past July" not in message
    assert "August event" not in message

def test_molly_core_includes_all_actor_reminder_calendars_for_upcoming(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")

    state_store.init_db()
    repo = CalendarRepository.from_config()
    core = MollyCore(repo)

    service = repo.service
    today = utils._today_local()
    repo.backend_module.add_event(service, {"calendar": "sunghwan", "title": "AWS Summit London 2026", "date": today, "start": "08:00", "end": "18:30"})
    repo.backend_module.add_event(service, {"calendar": "haneul", "title": "Beavers", "date": today, "start": "17:30", "end": "18:45"})
    repo.backend_module.add_event(service, {"calendar": "younha", "title": "Alpha-Math", "date": today, "start": "19:00", "end": "20:00"})
    repo.backend_module.add_event(service, {"calendar": "family", "title": "Dover ferry", "date": today, "start": "21:00", "end": "22:00"})

    resolution = IntentResolution(
        status=ResolutionStatus.READY,
        intent=ScheduleIntent(
            action=IntentAction.VIEW_RANGE,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input="Upcoming",
            limit=10,
            metadata={"command": "upcoming"},
        ),
    )

    message = core.execute_resolution(resolution, user_id=8793305621)

    assert "Upcoming (JeeYoung calendars, next 10):" in message
    assert "[성환]" in message
    assert "[하늘]" in message
    assert "[윤하]" in message
    assert "[가족]" in message


def test_molly_core_includes_all_actor_reminder_calendars_for_next(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")

    state_store.init_db()
    repo = CalendarRepository.from_config()
    core = MollyCore(repo)

    service = repo.service
    today = utils._today_local()
    repo.backend_module.add_event(service, {"calendar": "sunghwan", "title": "Earliest shared event", "date": today, "start": "08:00", "end": "09:00"})
    repo.backend_module.add_event(service, {"calendar": "family", "title": "Later shared event", "date": today, "start": "09:30", "end": "10:00"})

    resolution = IntentResolution(
        status=ResolutionStatus.READY,
        intent=ScheduleIntent(
            action=IntentAction.VIEW_RANGE,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input="Next",
            metadata={"command": "next"},
        ),
    )

    message = core.execute_resolution(resolution, user_id=8793305621)

    assert "Next event (JeeYoung calendars):" in message
    assert "Earliest shared event" in message
    assert "Later shared event" not in message


def test_molly_core_rejects_unverifiable_created_event(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")

    state_store.init_db()
    repo = CalendarRepository.from_config()
    core = MollyCore(repo)

    original = repo.get_event_by_id
    def fake_get_event_by_id(event_id):
        event = original(event_id)
        if event is None:
            return None
        event["end"]["dateTime"] = utils.make_datetime(utils._today_local(), "12:30").isoformat()
        return event
    repo.get_event_by_id = fake_get_event_by_id

    resolution = IntentResolution(
        status=ResolutionStatus.READY,
        intent=ScheduleIntent(
            action=IntentAction.CREATE_EVENT,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input="test",
            target_calendar="haneul",
            title="Beavers camp",
            target_date=utils._today_local(),
            time_range=TimeRange(start="09:00", end="11:30"),
            metadata={"all_day": False},
        ),
    )

    message = core.execute_resolution(resolution, user_id=123)

    assert message.startswith("❌ Saved event end time did not match")


def test_molly_core_executes_explicit_month_view(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")

    state_store.init_db()
    repo = CalendarRepository.from_config()
    core = MollyCore(repo)

    service = repo.service
    repo.backend_module.add_event(service, {"calendar": "family", "title": "July trip", "date": __import__("datetime").date(2026, 7, 10), "start": "09:00", "end": "10:00"})
    repo.backend_module.add_event(service, {"calendar": "family", "title": "May thing", "date": __import__("datetime").date(2026, 5, 10), "start": "09:00", "end": "10:00"})

    resolution = IntentResolution(
        status=ResolutionStatus.READY,
        intent=ScheduleIntent(
            action=IntentAction.VIEW_RANGE,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input="Show me July schedule",
            metadata={"command": "month:2026-07"},
        ),
    )

    message = core.execute_resolution(resolution, user_id=123)

    assert "July 2026" in message
    assert "July trip" in message
    assert "May thing" not in message
