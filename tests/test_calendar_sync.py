from datetime import date

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
