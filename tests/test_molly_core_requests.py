from intent_models import IntentAction, ResolutionStatus
from molly_core_requests import resolution_from_request


def test_resolution_from_request_builds_create_event_intent():
    resolution = resolution_from_request(
        {
            "action": "create_event",
            "target_calendar": "younha",
            "title": "Tennis",
            "target_date": "2026-04-16",
            "start_time": "17:00",
            "end_time": "18:00",
            "all_day": False,
        }
    )

    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.CREATE_EVENT
    assert resolution.intent.target_calendar == "younha"
    assert resolution.intent.title == "Tennis"
    assert resolution.intent.target_date.isoformat() == "2026-04-16"
    assert resolution.intent.time_range is not None
    assert resolution.intent.time_range.start == "17:00"


def test_resolution_from_request_builds_timed_multiday_create_event_intent():
    resolution = resolution_from_request(
        {
            "action": "create_event",
            "target_calendar": "younha",
            "title": "Cub Indoor Camp",
            "target_date": "2026-04-17",
            "end_date": "2026-04-19",
            "start_time": "18:45",
            "end_time": "16:00",
            "all_day": False,
        }
    )

    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.date_range is not None
    assert resolution.intent.date_range.end.isoformat() == "2026-04-19"
    assert resolution.intent.time_range is not None
    assert resolution.intent.time_range.end == "16:00"


def test_resolution_from_request_builds_recurring_create_event_intent():
    resolution = resolution_from_request(
        {
            "action": "create_event",
            "target_calendar": "younha",
            "title": "Alpha-Math",
            "target_date": "2026-04-17",
            "start_time": "17:00",
            "end_time": "18:00",
            "all_day": False,
            "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=FR"],
        }
    )

    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.CREATE_EVENT
    assert resolution.intent.recurrence == ["RRULE:FREQ=WEEKLY;BYDAY=FR"]


def test_resolution_from_request_rejects_unknown_calendar():
    try:
        resolution_from_request(
            {
                "action": "create_event",
                "target_calendar": "unknown",
                "title": "Tennis",
                "target_date": "2026-04-16",
                "start_time": "17:00",
                "end_time": "18:00",
            }
        )
    except ValueError as exc:
        assert "Unknown target_calendar" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_resolution_from_request_builds_view_upcoming_intent():
    resolution = resolution_from_request(
        {
            "action": "view",
            "scope": "upcoming",
            "target_calendar": "younha",
            "limit": 5,
        }
    )

    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.VIEW_RANGE
    assert resolution.intent.target_calendar == "younha"
    assert resolution.intent.limit == 5
    assert resolution.intent.metadata["command"] == "upcoming"


def test_resolution_from_request_builds_search_intent():
    resolution = resolution_from_request(
        {
            "action": "search",
            "query": "Tennis",
        }
    )

    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.SEARCH
    assert resolution.intent.search_query == "Tennis"


def test_resolution_from_request_builds_delete_event_intent():
    resolution = resolution_from_request(
        {
            "action": "delete_event",
            "target_calendar": "younha",
            "title": "Tennis",
            "target_date": "2026-04-16",
        }
    )

    assert resolution.intent.action == IntentAction.DELETE_EVENT
    assert resolution.intent.target_calendar == "younha"
    assert resolution.intent.title == "Tennis"


def test_resolution_from_request_builds_update_event_intent():
    resolution = resolution_from_request(
        {
            "action": "update_event",
            "target_calendar": "younha",
            "title": "Tennis",
            "target_date": "2026-04-16",
            "changes": {
                "start_time": "18:00",
                "end_time": "19:00",
            },
        }
    )

    assert resolution.intent.action == IntentAction.UPDATE_EVENT
    assert resolution.intent.changes["start"] == "18:00"
    assert resolution.intent.changes["end"] == "19:00"


def test_resolution_from_request_defaults_missing_end_time_for_one_off_timed_event():
    resolution = resolution_from_request(
        {
            "action": "create_event",
            "target_calendar": "family",
            "title": "Ferry",
            "target_date": "2026-04-16",
            "start_time": "17:00",
            "all_day": False,
        }
    )

    assert resolution.intent.time_range is not None
    assert resolution.intent.time_range.start == "17:00"
    assert resolution.intent.time_range.end == "18:00"


def test_resolution_from_request_accepts_calendar_aliases_for_create():
    resolution = resolution_from_request(
        {
            "action": "create_event",
            "target_calendar": "윤하",
            "title": "Tennis",
            "target_date": "2026-04-16",
            "start_time": "17:00",
            "end_time": "18:00",
            "all_day": False,
        }
    )

    assert resolution.intent.target_calendar == "younha"


def test_resolution_from_request_builds_move_event_intent():
    resolution = resolution_from_request(
        {
            "action": "move_event",
            "source_calendar": "family",
            "target_calendar": "윤하",
            "title": "Sutton mock test",
            "target_date": "2026-05-17",
        }
    )

    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.MOVE_EVENT
    assert resolution.intent.source_calendar == "family"
    assert resolution.intent.target_calendar == "younha"
    assert resolution.intent.target_date.isoformat() == "2026-05-17"
