from datetime import date

import calendar_sync
from calendar_sync import LocalEventForSync, _google_has_equivalent_event, _to_google_add_command


def test_to_google_add_command_for_timed_event():
    event = LocalEventForSync(
        calendar_key="younha",
        summary="Tennis",
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
        start_time="17:00",
        end_time="18:00",
        all_day=False,
        recurrence=[],
    )

    command = _to_google_add_command(event)

    assert command["calendar"] == "younha"
    assert command["title"] == "Tennis"
    assert command["start"] == "17:00"
    assert command["end"] == "18:00"


def test_google_equivalence_matches_all_day_event():
    event = LocalEventForSync(
        calendar_key="family",
        summary="Picnic",
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
        start_time=None,
        end_time=None,
        all_day=True,
        recurrence=[],
    )

    google_events = [{
        "summary": "Picnic",
        "start": {"date": "2026-04-24"},
        "end": {"date": "2026-04-25"},
        "recurrence": [],
    }]

    assert _google_has_equivalent_event(google_events, event) is True


def test_sync_local_to_google_only_compares_same_calendar(monkeypatch):
    local_event = {
        "_calendar_name": "Younha",
        "summary": "Tennis",
        "start": {"dateTime": "2026-04-24T17:00:00+01:00"},
        "end": {"dateTime": "2026-04-24T18:00:00+01:00"},
        "recurrence": [],
    }
    other_calendar_google_event = {
        "_calendar_name": "Family",
        "summary": "Tennis",
        "start": {"dateTime": "2026-04-24T17:00:00+01:00"},
        "end": {"dateTime": "2026-04-24T18:00:00+01:00"},
        "recurrence": [],
    }

    monkeypatch.setattr(calendar_sync.local_calendar_backend, "authenticate", lambda: object())
    monkeypatch.setattr(calendar_sync.google_calendar_backend, "authenticate", lambda: object())
    monkeypatch.setattr(
        calendar_sync.local_calendar_backend,
        "list_events_range",
        lambda *_args: [local_event],
    )

    requested_google_calendars = []

    def fake_list_events_range_for_calendar(_service, calendar_key, _start, _end):
        requested_google_calendars.append(calendar_key)
        if calendar_key == "family":
            return [other_calendar_google_event]
        return []

    monkeypatch.setattr(
        calendar_sync.google_calendar_backend,
        "list_events_range_for_calendar",
        fake_list_events_range_for_calendar,
    )

    summary, details = calendar_sync.sync_local_to_google(
        date(2026, 4, 24),
        date(2026, 4, 24),
        dry_run=True,
        calendar_keys=["younha"],
    )

    assert requested_google_calendars == ["younha"]
    assert summary.inserted == 1
    assert summary.skipped_existing == 0
    assert details == ["DRY-RUN insert | younha | Tennis | 2026-04-24 17:00-18:00"]
