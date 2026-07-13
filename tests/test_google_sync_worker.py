from datetime import date

import calendar_sync
import config
import state_store


def setup_function():
    if config.STATE_DB_PATH.exists():
        config.STATE_DB_PATH.unlink()
    state_store.init_db()


def test_process_google_sync_outbox_inserts_create(monkeypatch):
    calls = []

    monkeypatch.setattr(config, "CALENDARS", {"younha": "google-younha"})
    monkeypatch.setattr(calendar_sync.google_calendar_backend, "authenticate", lambda: object())
    monkeypatch.setattr(
        calendar_sync.google_calendar_backend,
        "list_events_range_for_calendar",
        lambda *_args: [],
    )
    monkeypatch.setattr(
        calendar_sync.google_calendar_backend,
        "add_event",
        lambda _service, command: calls.append(command) or "✅ Added",
    )
    outbox_id = state_store.enqueue_google_sync(
        operation="create",
        payload={
            "action": "create_event",
            "target_calendar": "younha",
            "title": "Tennis",
            "target_date": "2026-04-24",
            "time_range": {"start": "17:00", "end": "18:00"},
            "recurrence": [],
            "metadata": {"all_day": False},
        },
    )

    summary, details = calendar_sync.process_google_sync_outbox_once()
    stored = state_store.get_google_sync_outbox_item(outbox_id)

    assert summary.processed == 1
    assert summary.inserted == 1
    assert calls[0]["calendar"] == "younha"
    assert calls[0]["date"] == date(2026, 4, 24)
    assert stored["status"] == "done"
    assert stored["google_calendar_id"] == "google-younha"
    mapping = state_store.get_google_event_mapping(calendar_sync._outbox_idempotency_key(stored))
    assert mapping is not None
    assert "INSERTED" in details[0]


def test_process_google_sync_outbox_records_google_event_id_after_insert(monkeypatch):
    calls = []

    monkeypatch.setattr(config, "CALENDARS", {"younha": "google-younha"})
    monkeypatch.setattr(
        config,
        "CALENDAR_DISPLAY_NAMES",
        {"younha": "YounHa"},
    )
    monkeypatch.setattr(calendar_sync.google_calendar_backend, "authenticate", lambda: object())

    def fake_list_events_range_for_calendar(*_args):
        if not calls:
            return []
        return [
            {
                "id": "google-event-123",
                "_calendar_name": "YounHa",
                "summary": "Tennis",
                "start": {"dateTime": "2026-04-24T17:00:00+01:00"},
                "end": {"dateTime": "2026-04-24T18:00:00+01:00"},
                "recurrence": [],
            }
        ]

    monkeypatch.setattr(
        calendar_sync.google_calendar_backend,
        "list_events_range_for_calendar",
        fake_list_events_range_for_calendar,
    )
    monkeypatch.setattr(
        calendar_sync.google_calendar_backend,
        "add_event",
        lambda _service, command: calls.append(command) or "✅ Added",
    )
    outbox_id = state_store.enqueue_google_sync(
        operation="create",
        payload={
            "action": "create_event",
            "target_calendar": "younha",
            "title": "Tennis",
            "target_date": "2026-04-24",
            "time_range": {"start": "17:00", "end": "18:00"},
            "recurrence": [],
            "metadata": {"all_day": False},
        },
    )

    summary, _details = calendar_sync.process_google_sync_outbox_once()
    stored = state_store.get_google_sync_outbox_item(outbox_id)
    mapping = state_store.get_google_event_mapping(calendar_sync._outbox_idempotency_key(stored))

    assert summary.inserted == 1
    assert stored["google_event_id"] == "google-event-123"
    assert mapping["google_event_id"] == "google-event-123"


def test_process_google_sync_outbox_skips_previously_mapped_create(monkeypatch):
    calls = []
    monkeypatch.setattr(config, "CALENDARS", {"family": "google-family"})
    outbox_id = state_store.enqueue_google_sync(
        operation="create",
        payload={
            "action": "create_event",
            "target_calendar": "family",
            "title": "Picnic",
            "target_date": "2026-04-24",
            "time_range": None,
            "recurrence": [],
            "metadata": {"all_day": True},
        },
    )
    row = state_store.get_google_sync_outbox_item(outbox_id)
    state_store.upsert_google_event_mapping(
        idempotency_key=calendar_sync._outbox_idempotency_key(row),
        operation="create",
        google_calendar_id="google-family",
        google_event_id="google-event-existing",
        outbox_id=99,
    )
    monkeypatch.setattr(
        calendar_sync.google_calendar_backend,
        "add_event",
        lambda _service, command: calls.append(command) or "✅ Added",
    )

    summary, details = calendar_sync.process_google_sync_outbox_once()
    stored = state_store.get_google_sync_outbox_item(outbox_id)

    assert summary.skipped_existing == 1
    assert calls == []
    assert stored["status"] == "done"
    assert stored["google_event_id"] == "google-event-existing"
    assert "SKIP mapped" in details[0]


def test_process_google_sync_outbox_skips_existing(monkeypatch):
    monkeypatch.setattr(config, "CALENDARS", {"family": "google-family"})
    monkeypatch.setattr(
        config,
        "CALENDAR_DISPLAY_NAMES",
        {"family": "Family"},
    )
    monkeypatch.setattr(calendar_sync.google_calendar_backend, "authenticate", lambda: object())
    monkeypatch.setattr(
        calendar_sync.google_calendar_backend,
        "list_events_range_for_calendar",
        lambda *_args: [
            {
                "_calendar_name": "Family",
                "summary": "Picnic",
                "start": {"date": "2026-04-24"},
                "end": {"date": "2026-04-25"},
                "recurrence": [],
            }
        ],
    )
    outbox_id = state_store.enqueue_google_sync(
        operation="create",
        payload={
            "action": "create_event",
            "target_calendar": "family",
            "title": "Picnic",
            "target_date": "2026-04-24",
            "time_range": None,
            "recurrence": [],
            "metadata": {"all_day": True},
        },
    )

    summary, _details = calendar_sync.process_google_sync_outbox_once()
    stored = state_store.get_google_sync_outbox_item(outbox_id)
    mapping = state_store.get_google_event_mapping(calendar_sync._outbox_idempotency_key(stored))

    assert summary.skipped_existing == 1
    assert stored["status"] == "done"
    assert mapping is not None


def test_process_google_sync_outbox_marks_unsupported_operation():
    outbox_id = state_store.enqueue_google_sync(
        operation="delete",
        payload={"action": "delete_event", "target_calendar": "family", "title": "Picnic"},
    )

    summary, details = calendar_sync.process_google_sync_outbox_once()
    stored = state_store.get_google_sync_outbox_item(outbox_id)

    assert summary.unsupported == 1
    assert stored["status"] == "unsupported"
    assert "Unsupported Google sync operation" in stored["last_error"]
    assert "UNSUPPORTED" in details[0]


def test_process_google_sync_outbox_dry_run_does_not_claim():
    outbox_id = state_store.enqueue_google_sync(
        operation="create",
        payload={
            "action": "create_event",
            "target_calendar": "family",
            "title": "Picnic",
            "target_date": "2026-04-24",
            "time_range": None,
            "recurrence": [],
            "metadata": {"all_day": True},
        },
    )

    summary, details = calendar_sync.process_google_sync_outbox_once(dry_run=True)
    stored = state_store.get_google_sync_outbox_item(outbox_id)

    assert summary.processed == 1
    assert summary.inserted == 1
    assert stored["status"] == "pending"
    assert stored["attempts"] == 0
    assert "DRY-RUN insert" in details[0]
