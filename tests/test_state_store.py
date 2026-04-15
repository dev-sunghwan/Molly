from datetime import date

import config
import state_store
from intent_models import (
    ExecutionResult,
    IntentAction,
    IntentResolution,
    IntentSource,
    ResolutionStatus,
    ScheduleIntent,
    TimeRange,
)


def setup_function():
    if config.STATE_DB_PATH.exists():
        config.STATE_DB_PATH.unlink()
    state_store.init_db()


def test_pending_clarification_round_trip():
    resolution = IntentResolution(
        status=ResolutionStatus.NEEDS_CLARIFICATION,
        intent=ScheduleIntent(
            action=IntentAction.CREATE_EVENT,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input="add tennis tomorrow 17:00-18:00",
            title="tennis",
            target_date=date(2026, 4, 15),
            time_range=TimeRange(start="17:00", end="18:00"),
        ),
        missing_fields=["target_calendar"],
        clarification_prompt="Which family calendar should Molly use?",
    )

    state_store.save_pending_clarification(123, resolution)
    loaded = state_store.load_pending_clarification(123)

    assert loaded is not None
    assert loaded.status == ResolutionStatus.NEEDS_CLARIFICATION
    assert loaded.intent.title == "tennis"
    assert loaded.intent.time_range is not None
    assert loaded.intent.time_range.start == "17:00"
    assert loaded.missing_fields == ["target_calendar"]


def test_clear_pending_clarification():
    resolution = IntentResolution(
        status=ResolutionStatus.NEEDS_CLARIFICATION,
        intent=ScheduleIntent(
            action=IntentAction.CREATE_EVENT,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            title="tennis",
        ),
        missing_fields=["target_calendar"],
    )
    state_store.save_pending_clarification(123, resolution)

    state_store.clear_pending_clarification(123)

    assert state_store.load_pending_clarification(123) is None


def test_execution_log_round_trip():
    result = ExecutionResult(
        success=True,
        action=IntentAction.CREATE_EVENT,
        message="ok",
        metadata={"target_calendar": "younha"},
    )

    state_store.record_execution(123, result)
    rows = state_store.list_execution_log(limit=10)

    assert len(rows) == 1
    assert rows[0]["user_id"] == 123
    assert rows[0]["action"] == IntentAction.CREATE_EVENT.value
    assert rows[0]["success"] is True
    assert rows[0]["metadata"]["target_calendar"] == "younha"


def test_processed_input_round_trip():
    state_store.mark_processed_input(
        source="gmail",
        external_id="msg-123",
        status="processed",
        metadata={"subject": "Reminder"},
    )

    stored = state_store.get_processed_input("gmail", "msg-123")

    assert stored is not None
    assert stored["source"] == "gmail"
    assert stored["external_id"] == "msg-123"
    assert stored["status"] == "processed"
    assert stored["metadata"]["subject"] == "Reminder"
    assert state_store.is_processed_input("gmail", "msg-123") is True
