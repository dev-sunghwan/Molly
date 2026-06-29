from datetime import timedelta

import config
import state_store
import utils
from calendar_repository import CalendarRepository
from intent_models import (
    DateRange,
    IntentAction,
    IntentResolution,
    IntentSource,
    ResolutionStatus,
    ScheduleIntent,
    TimeRange,
)
from molly_core import MollyCore


def test_molly_core_enqueues_google_sync_after_local_create(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "GOOGLE_SYNC_OUTBOX_ENABLED", True)
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")

    state_store.init_db()
    repo = CalendarRepository.from_config()
    core = MollyCore(repo)
    today = utils._today_local()

    resolution = IntentResolution(
        status=ResolutionStatus.READY,
        intent=ScheduleIntent(
            action=IntentAction.CREATE_EVENT,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input="내일 윤하 테니스 넣어줘",
            target_calendar="younha",
            title="Tennis",
            target_date=today,
            time_range=TimeRange(start="17:00", end="18:00"),
            metadata={"all_day": False},
        ),
    )

    message = core.execute_resolution(resolution, user_id=123)
    rows = state_store.list_google_sync_outbox(status="pending")

    assert "Added to YounHa" in message
    assert len(rows) == 1
    assert rows[0]["operation"] == "create"
    assert rows[0]["payload"]["action"] == "create_event"
    assert rows[0]["payload"]["target_calendar"] == "younha"
    assert rows[0]["payload"]["title"] == "Tennis"
    assert rows[0]["payload"]["actor_user_id"] == 123
    assert rows[0]["local_event_id"] is not None
    assert rows[0]["payload"]["mutation_result"]["local_event_id"] == rows[0]["local_event_id"]
    assert rows[0]["payload"]["mutation_result"]["operation"] == "create"


def test_molly_core_enqueues_update_delete_with_mutation_result(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "GOOGLE_SYNC_OUTBOX_ENABLED", True)
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")

    state_store.init_db()
    repo = CalendarRepository.from_config()
    core = MollyCore(repo)
    today = utils._today_local()
    repo.add_event(
        {
            "calendar": "family",
            "title": "Mutation Contract",
            "date": today,
            "start": "14:00",
            "end": "15:00",
        }
    )

    update_resolution = IntentResolution(
        status=ResolutionStatus.READY,
        intent=ScheduleIntent(
            action=IntentAction.UPDATE_EVENT,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input="move mutation contract",
            target_calendar="family",
            title="Mutation Contract",
            target_date=today,
            changes={"start": "15:00", "end": "16:00"},
        ),
    )
    delete_resolution = IntentResolution(
        status=ResolutionStatus.READY,
        intent=ScheduleIntent(
            action=IntentAction.DELETE_EVENT,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input="delete mutation contract",
            target_calendar="family",
            title="Mutation Contract",
            target_date=today,
        ),
    )

    update_message = core.execute_resolution(update_resolution, user_id=123)
    delete_message = core.execute_resolution(delete_resolution, user_id=123)
    rows = state_store.list_google_sync_outbox(status="pending")
    update_row = next(row for row in rows if row["operation"] == "update")
    delete_row = next(row for row in rows if row["operation"] == "delete")

    assert "Updated in Family" in update_message
    assert "Deleted from Family" in delete_message
    assert update_row["local_event_id"] is not None
    assert delete_row["local_event_id"] == update_row["local_event_id"]
    assert update_row["payload"]["mutation_result"]["operation"] == "update"
    assert update_row["payload"]["mutation_result"]["start_time"] == "15:00"
    assert delete_row["payload"]["mutation_result"]["operation"] == "delete"
    assert delete_row["payload"]["mutation_result"]["title"] == "Mutation Contract"


def test_molly_core_does_not_enqueue_google_sync_for_failed_create(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "GOOGLE_SYNC_OUTBOX_ENABLED", True)
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")

    state_store.init_db()
    repo = CalendarRepository.from_config()
    core = MollyCore(repo)
    today = utils._today_local()

    resolution = IntentResolution(
        status=ResolutionStatus.READY,
        intent=ScheduleIntent(
            action=IntentAction.CREATE_EVENT,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input="반복 캠프",
            target_calendar="younha",
            title="Recurring Camp",
            target_date=today,
            date_range=DateRange(start=today, end=today + timedelta(days=1)),
            time_range=TimeRange(start="17:00", end="18:00"),
            recurrence=["RRULE:FREQ=WEEKLY;BYDAY=FR"],
            metadata={"all_day": False},
        ),
    )

    message = core.execute_resolution(resolution, user_id=123)
    rows = state_store.list_google_sync_outbox(status="pending")

    assert message.startswith("❌")
    assert rows == []
