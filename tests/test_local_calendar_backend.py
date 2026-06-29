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


def test_local_backend_finds_event_id_for_command(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")

    service = local_calendar_backend.authenticate()
    command = {
        "calendar": "younha",
        "title": "Alpha-Math",
        "date": utils._today_local(),
        "start": "17:00",
        "end": "18:00",
    }
    missing = local_calendar_backend.find_event_id_for_command(service, command)
    local_calendar_backend.add_event(service, command)
    found = local_calendar_backend.find_event_id_for_command(service, command)

    assert missing is None
    assert found is not None


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
    assert "Before:" in edit_message
    assert "14:00–15:00" in edit_message
    assert "After:" in edit_message
    assert "15:00–16:00" in edit_message
    assert "Deleted from SungHwan" in delete_message


def test_local_backend_mutation_results_include_local_event_id(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")

    service = local_calendar_backend.authenticate()
    today = utils._today_local()
    add_message, add_result = local_calendar_backend.add_event_result(
        service,
        {
            "calendar": "family",
            "title": "Mutation Contract",
            "date": today,
            "start": "14:00",
            "end": "15:00",
        },
    )
    edit_message, edit_result = local_calendar_backend.find_and_edit_event_result(
        service,
        "family",
        today,
        "Mutation Contract",
        {"start": "15:00", "end": "16:00"},
    )
    delete_message, delete_result = local_calendar_backend.find_and_delete_event_result(
        service,
        "family",
        today,
        "Mutation Contract",
    )

    assert "Added to Family" in add_message
    assert add_result.local_event_id is not None
    assert add_result.operation == "create"
    assert add_result.target_calendar == "family"
    assert add_result.target_date == today
    assert add_result.start_time == "14:00"

    assert "Updated in Family" in edit_message
    assert "Before:" in edit_message
    assert "14:00–15:00" in edit_message
    assert "After:" in edit_message
    assert "15:00–16:00" in edit_message
    assert edit_result.local_event_id == add_result.local_event_id
    assert edit_result.operation == "update"
    assert edit_result.start_time == "15:00"
    assert edit_result.end_time == "16:00"

    assert "Deleted from Family" in delete_message
    assert delete_result.local_event_id == add_result.local_event_id
    assert delete_result.operation == "delete"
    assert delete_result.title == "Mutation Contract"


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


def test_local_backend_rejects_recurring_multiday_event(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")

    service = local_calendar_backend.authenticate()
    message = local_calendar_backend.add_event(
        service,
        {
            "calendar": "younha",
            "title": "Tennis Avenue",
            "date": utils.parse_date("30-04-2026"),
            "end_date": utils.parse_date("31-07-2026"),
            "start": "18:30",
            "end": "20:00",
            "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=TH"],
        },
    )

    events = local_calendar_backend.list_events_range(
        service,
        utils.parse_date("30-04-2026"),
        utils.parse_date("31-07-2026"),
    )

    assert message.startswith("❌ Recurring events cannot span multiple days")
    assert events == []


def test_local_backend_can_delete_one_recurring_occurrence(monkeypatch, tmp_path):
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

    delete_message = local_calendar_backend.find_and_delete_event(
        service,
        "younha",
        utils.parse_date("20-04-2026"),
        "Cubs",
    )

    deleted_day = local_calendar_backend.list_events(service, utils.parse_date("20-04-2026"))
    next_day = local_calendar_backend.list_events(service, utils.parse_date("27-04-2026"))

    assert "Deleted occurrence from YounHa" in delete_message
    assert deleted_day == []
    assert len(next_day) == 1
    assert next_day[0]["summary"] == "Cubs"


def test_local_backend_recurring_occurrence_delete_requires_date(monkeypatch, tmp_path):
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

    delete_message = local_calendar_backend.find_and_delete_event(
        service,
        "younha",
        None,
        "Cubs",
    )

    assert "Specify a date to delete one occurrence" in delete_message
