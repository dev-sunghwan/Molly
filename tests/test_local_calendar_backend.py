from datetime import timedelta

import config
import local_calendar_backend
import utils


def test_local_backend_add_and_list_event(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")

    service = local_calendar_backend.authenticate()
    message = local_calendar_backend.add_event(
        service,
        {
            "calendar": "younha",
            "title": "Tennis",
            "date": utils._today_local(),
            "start": "17:00",
            "end": "18:00",
        },
    )

    events = local_calendar_backend.list_events(service, utils._today_local())

    assert "Added to YounHa" in message
    assert len(events) == 1
    assert events[0]["summary"] == "Tennis"
    assert events[0]["_calendar_name"] == "YounHa"


def test_local_backend_recurring_event_expands(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")

    service = local_calendar_backend.authenticate()
    today = utils._today_local()
    next_monday = utils.parse_date("mon")
    local_calendar_backend.add_event(
        service,
        {
            "calendar": "younha",
            "title": "Swimming",
            "date": next_monday,
            "all_day": True,
            "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO"],
        },
    )

    events = local_calendar_backend.list_events_range(service, today, today + timedelta(days=21))

    assert len(events) >= 2
    assert all(event["summary"] == "Swimming" for event in events)
    assert all(event.get("recurringEventId") for event in events)


def test_local_backend_edit_and_delete_non_recurring(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")

    service = local_calendar_backend.authenticate()
    today = utils._today_local()
    local_calendar_backend.add_event(
        service,
        {
            "calendar": "sunghwan",
            "title": "Dentist",
            "date": today,
            "start": "14:00",
            "end": "15:00",
        },
    )

    edit_message = local_calendar_backend.find_and_edit_event(
        service,
        "sunghwan",
        today,
        "Dentist",
        {"start": "15:00", "end": "16:00"},
    )
    delete_message = local_calendar_backend.find_and_delete_event(
        service,
        "sunghwan",
        today,
        "Dentist",
    )

    assert "Updated in SungHwan" in edit_message
    assert "15:00–16:00" in edit_message
    assert "Deleted from SungHwan" in delete_message
