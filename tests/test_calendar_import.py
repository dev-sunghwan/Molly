from datetime import date

import calendar_import


def test_normalize_google_timed_event():
    payload = calendar_import._normalize_google_event(
        {
            "start": {"dateTime": "2026-04-16T18:30:00+01:00"},
            "end": {"dateTime": "2026-04-16T20:00:00+01:00"},
        }
    )

    assert payload == {
        "all_day": False,
        "start_date": date(2026, 4, 16),
        "end_date": date(2026, 4, 16),
        "start_time": "18:30",
        "end_time": "20:00",
    }


def test_normalize_google_all_day_event():
    payload = calendar_import._normalize_google_event(
        {
            "start": {"date": "2026-04-16"},
            "end": {"date": "2026-04-17"},
        }
    )

    assert payload == {
        "all_day": True,
        "start_date": date(2026, 4, 16),
        "end_date": date(2026, 4, 16),
        "start_time": None,
        "end_time": None,
    }


def test_supported_weekly_recurrence_only():
    assert calendar_import._is_supported_recurrence(["RRULE:FREQ=WEEKLY;BYDAY=MO"])
    assert not calendar_import._is_supported_recurrence(["RRULE:FREQ=DAILY"])
    assert not calendar_import._is_supported_recurrence(
        ["RRULE:FREQ=WEEKLY;BYDAY=MO", "EXDATE:20260420"]
    )
