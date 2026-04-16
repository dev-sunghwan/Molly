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
