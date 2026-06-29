import tempfile
from datetime import date
from pathlib import Path

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
    config.STATE_DB_PATH = Path(tempfile.mkdtemp(prefix="molly-state-store-test-")) / "molly_state.db"
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


def test_inbound_command_round_trip():
    stored = state_store.record_inbound_command(
        request_id="telegram-msg-123",
        source="telegram",
        source_message_id="msg-123",
        source_user_id="8289",
        source_user_name="SungHwan",
        source_channel_id="direct",
        raw_text="내일 윤하 테니스 17:00",
        raw_payload={"text": "내일 윤하 테니스 17:00"},
    )

    loaded = state_store.get_command_by_request_id("telegram-msg-123")

    assert loaded is not None
    assert loaded["id"] == stored["id"]
    assert loaded["request_id"] == "telegram-msg-123"
    assert loaded["source"] == "telegram"
    assert loaded["source_message_id"] == "msg-123"
    assert loaded["source_user_id"] == "8289"
    assert loaded["source_user_name"] == "SungHwan"
    assert loaded["source_channel_id"] == "direct"
    assert loaded["raw_text"] == "내일 윤하 테니스 17:00"
    assert loaded["raw_payload"]["text"] == "내일 윤하 테니스 17:00"
    assert loaded["status"] == "received"


def test_inbound_command_request_id_is_idempotent():
    first = state_store.record_inbound_command(
        request_id="slack-msg-123",
        source="slack",
        raw_text="today",
        raw_payload={"text": "today"},
    )
    second = state_store.record_inbound_command(
        request_id="slack-msg-123",
        source="slack",
        raw_text="tomorrow",
        raw_payload={"text": "tomorrow"},
    )

    assert second["id"] == first["id"]
    assert second["raw_text"] == "today"
    assert second["raw_payload"]["text"] == "today"


def test_update_command_status():
    state_store.record_inbound_command(
        request_id="telegram-msg-456",
        source="telegram",
        raw_text="today",
        raw_payload={"text": "today"},
    )

    updated = state_store.update_command_status(
        "telegram-msg-456",
        "validated",
        parser_version="command-v1",
        structured_payload={"action": "view", "scope": "today"},
        execution_result={"success": True, "message": "ok"},
    )

    assert updated["status"] == "validated"
    assert updated["parser_version"] == "command-v1"
    assert updated["structured_payload"]["action"] == "view"
    assert updated["execution_result"]["success"] is True


def test_update_command_reply_status():
    state_store.record_inbound_command(
        request_id="telegram-reply-1",
        source="telegram",
        raw_text="today",
        raw_payload={"text": "today"},
    )

    updated = state_store.update_command_reply_status("telegram-reply-1", "resent")

    assert updated["reply_status"] == "resent"
    assert updated["reply_error"] is None
    assert updated["reply_attempts"] == 1
    assert updated["last_reply_at"] is not None


def test_list_commands_filters_and_counts_by_status():
    state_store.record_inbound_command(
        request_id="telegram-list-1",
        source="telegram",
        raw_text="today",
        raw_payload={"text": "today"},
    )
    state_store.record_inbound_command(
        request_id="slack-list-1",
        source="slack",
        raw_text="bad",
        raw_payload={"text": "bad"},
    )
    state_store.update_command_status(
        "slack-list-1",
        "failed",
        execution_result={"success": False, "error": "boom"},
    )

    failed = state_store.list_commands(status="failed")
    telegram = state_store.list_commands(source="telegram")
    counts = state_store.count_commands_by_status()

    assert [row["request_id"] for row in failed] == ["slack-list-1"]
    assert [row["request_id"] for row in telegram] == ["telegram-list-1"]
    assert counts == {"failed": 1, "received": 1}


def test_google_sync_outbox_round_trip():
    outbox_id = state_store.enqueue_google_sync(
        operation="create",
        payload={
            "action": "create_event",
            "target_calendar": "younha",
            "title": "Tennis",
        },
    )

    rows = state_store.list_google_sync_outbox(status="pending")

    assert len(rows) == 1
    assert rows[0]["id"] == outbox_id
    assert rows[0]["operation"] == "create"
    assert rows[0]["status"] == "pending"
    assert rows[0]["attempts"] == 0
    assert rows[0]["payload"]["title"] == "Tennis"


def test_count_google_sync_outbox_by_status():
    state_store.enqueue_google_sync(
        operation="create",
        payload={"action": "create_event", "target_calendar": "family", "title": "Picnic"},
    )
    outbox_id = state_store.enqueue_google_sync(
        operation="create",
        payload={"action": "create_event", "target_calendar": "younha", "title": "Tennis"},
    )
    state_store.claim_google_sync_outbox_item(outbox_id)
    state_store.mark_google_sync_outbox_done(outbox_id)

    counts = state_store.count_google_sync_outbox_by_status()

    assert counts == {"done": 1, "pending": 1}


def test_google_sync_outbox_lifecycle():
    outbox_id = state_store.enqueue_google_sync(
        operation="create",
        payload={"action": "create_event", "target_calendar": "family", "title": "Picnic"},
    )

    claimed = state_store.claim_google_sync_outbox_item(outbox_id)
    duplicate_claim = state_store.claim_google_sync_outbox_item(outbox_id)
    done = state_store.mark_google_sync_outbox_done(
        outbox_id,
        google_calendar_id="family-google-id",
        google_event_id="google-event-123",
    )

    assert claimed is not None
    assert claimed["status"] == "processing"
    assert claimed["attempts"] == 1
    assert duplicate_claim is None
    assert done["status"] == "done"
    assert done["google_calendar_id"] == "family-google-id"
    assert done["google_event_id"] == "google-event-123"


def test_google_sync_outbox_failed_retry_returns_to_pending():
    outbox_id = state_store.enqueue_google_sync(
        operation="create",
        payload={"action": "create_event", "target_calendar": "family", "title": "Picnic"},
    )
    state_store.claim_google_sync_outbox_item(outbox_id)

    failed = state_store.mark_google_sync_outbox_failed(outbox_id, "temporary outage", retry=True)

    assert failed["status"] == "pending"
    assert failed["attempts"] == 1
    assert failed["last_error"] == "temporary outage"


def test_google_event_mapping_round_trip_and_update():
    first = state_store.upsert_google_event_mapping(
        idempotency_key="google-sync-key-1",
        operation="create",
        google_calendar_id="google-family",
        google_event_id=None,
        local_event_id="local-1",
        outbox_id=10,
    )
    second = state_store.upsert_google_event_mapping(
        idempotency_key="google-sync-key-1",
        operation="create",
        google_calendar_id="google-family",
        google_event_id="google-event-1",
    )

    loaded = state_store.get_google_event_mapping("google-sync-key-1")

    assert first["id"] == second["id"]
    assert loaded["local_event_id"] == "local-1"
    assert loaded["outbox_id"] == 10
    assert loaded["google_calendar_id"] == "google-family"
    assert loaded["google_event_id"] == "google-event-1"


def test_email_candidate_round_trip():
    candidate_id = state_store.save_email_candidate(
        message_id="msg-555",
        status="ready",
        reason="Enough information.",
        summary="Alpha-Math | calendar=younha | date=2026-04-17",
        candidate_payload={
            "status": "ready",
            "message_id": "msg-555",
            "reason": "Enough information.",
            "summary": "Alpha-Math | calendar=younha | date=2026-04-17",
            "missing_fields": [],
            "intent": {
                "action": "create_event",
                "source": "email",
                "raw_input": "Registration confirmation",
                "target_calendar": "younha",
                "title": "Alpha-Math",
                "target_date": "2026-04-17",
                "date_range": None,
                "time_range": {"start": "17:00", "end": "18:00"},
                "recurrence": [],
                "search_query": None,
                "help_topic": None,
                "limit": None,
                "changes": {},
                "metadata": {"email_message_id": "msg-555"},
            },
        },
        metadata={"subject": "Registration confirmation"},
    )

    stored = state_store.get_email_candidate(candidate_id)

    assert stored is not None
    assert stored["message_id"] == "msg-555"
    assert stored["decision_status"] == "pending_confirmation"
    assert stored["candidate"]["intent"]["title"] == "Alpha-Math"
    assert stored["metadata"]["subject"] == "Registration confirmation"


def test_mark_email_candidate_notified_and_ignore():
    candidate_id = state_store.save_email_candidate(
        message_id="msg-777",
        status="ready",
        reason="Enough information.",
        summary="Alpha-Math",
        candidate_payload={"status": "ready", "message_id": "msg-777", "intent": None},
        metadata={},
    )

    state_store.mark_email_candidate_notified(candidate_id)
    state_store.update_email_candidate_decision(
        candidate_id,
        "ignored",
        metadata_updates={"ignored_by_user_id": 1},
    )

    stored = state_store.get_email_candidate(candidate_id)
    assert stored is not None
    assert stored["notified"] is True
    assert stored["decision_status"] == "ignored"
    assert stored["metadata"]["ignored_by_user_id"] == 1
