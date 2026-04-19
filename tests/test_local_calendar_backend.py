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


def test_local_backend_recurring_timed_event_uses_occurrence_date(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")

    service = local_calendar_backend.authenticate()
    local_calendar_backend.add_event(
        service,
        {
            "calendar": "haneul",
            "title": "swimming",
            "date": utils.parse_date("10-04-2026"),
            "start": "18:00",
            "end": "18:30",
            "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=FR"],
        },
    )

    events = local_calendar_backend.list_events(service, utils.parse_date("17-04-2026"))

    assert len(events) == 1
    assert events[0]["summary"] == "swimming"
    assert events[0]["start"]["dateTime"].startswith("2026-04-17T18:00")
    assert events[0]["end"]["dateTime"].startswith("2026-04-17T18:30")


def test_local_backend_blocks_exact_duplicate_event(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")

    service = local_calendar_backend.authenticate()
    today = utils._today_local()
    first_message = local_calendar_backend.add_event(
        service,
        {
            "calendar": "younha",
            "title": "Alpha-Math",
            "date": today,
            "start": "17:00",
            "end": "18:00",
        },
    )
    second_message = local_calendar_backend.add_event(
        service,
        {
            "calendar": "younha",
            "title": "Alpha-Math",
            "date": today,
            "start": "17:00",
            "end": "18:00",
        },
    )

    events = local_calendar_backend.list_events(service, today)

    assert "Added to YounHa" in first_message
    assert "Already exists in YounHa" in second_message
    assert len(events) == 1
    assert events[0]["summary"] == "Alpha-Math"


def test_local_backend_blocks_same_slot_when_recurrence_differs(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")

    service = local_calendar_backend.authenticate()
    today = utils._today_local()
    local_calendar_backend.add_event(
        service,
        {
            "calendar": "younha",
            "title": "Alpha-Math",
            "date": today,
            "start": "17:00",
            "end": "18:00",
        },
    )
    recurring_message = local_calendar_backend.add_event(
        service,
        {
            "calendar": "younha",
            "title": "Alpha-Math",
            "date": today,
            "start": "17:00",
            "end": "18:00",
            "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=FR"],
        },
    )

    events = local_calendar_backend.list_events(service, today)

    assert "Already exists in YounHa" in recurring_message
    assert len(events) == 1
    assert events[0]["summary"] == "Alpha-Math"


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


def test_local_backend_timed_multiday_event_lists_across_days(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")

    service = local_calendar_backend.authenticate()
    local_calendar_backend.add_event(
        service,
        {
            "calendar": "younha",
            "title": "Cub Indoor Camp",
            "date": utils.parse_date("17-04-2026"),
            "end_date": utils.parse_date("19-04-2026"),
            "start": "18:45",
            "end": "16:00",
            "all_day": False,
        },
    )

    middle_day_events = local_calendar_backend.list_events(service, utils.parse_date("18-04-2026"))

    assert len(middle_day_events) == 1
    assert middle_day_events[0]["summary"] == "Cub Indoor Camp"
    assert middle_day_events[0]["start"]["dateTime"].startswith("2026-04-17T18:45")
    assert middle_day_events[0]["end"]["dateTime"].startswith("2026-04-19T16:00")

def test_local_backend_recurring_occurrence_override_applies_only_to_one_date(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")

    service = local_calendar_backend.authenticate()
    local_calendar_backend.add_event(
        service,
        {
            "calendar": "younha",
            "title": "Cubs",
            "date": utils.parse_date("13-04-2026"),
            "start": "18:30",
            "end": "20:00",
            "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO"],
        },
    )

    message = local_calendar_backend.set_recurring_occurrence_override(
        service,
        "younha",
        "Cubs",
        utils.parse_date("20-04-2026"),
        changes={"title": "Cubs @ Green Lane Primary School"},
        metadata={"location": "Green Lane Primary School"},
    )

    special = local_calendar_backend.list_events(service, utils.parse_date("20-04-2026"))
    normal = local_calendar_backend.list_events(service, utils.parse_date("27-04-2026"))

    assert "Updated occurrence in YounHa" in message
    assert len(special) == 1
    assert special[0]["summary"] == "Cubs @ Green Lane Primary School"
    assert special[0]["location"] == "Green Lane Primary School"
    assert len(normal) == 1
    assert normal[0]["summary"] == "Cubs"
