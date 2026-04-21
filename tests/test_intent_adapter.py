"""
tests/test_intent_adapter.py — Unit tests for shared intent translation.
"""
from datetime import date

import commands
from intent_adapter import command_to_intent, parse_text_to_intent
from intent_models import IntentAction, ResolutionStatus


def test_add_command_maps_to_create_intent():
    resolution = parse_text_to_intent(
        "add YounHa tennis 15-04-2026 17:00-18:00",
        commands.parse,
    )

    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.CREATE_EVENT
    assert resolution.intent.target_calendar == "younha"
    assert resolution.intent.title == "tennis"
    assert resolution.intent.target_date == date(2026, 4, 15)
    assert resolution.intent.time_range is not None
    assert resolution.intent.time_range.start == "17:00"
    assert resolution.intent.time_range.end == "18:00"


def test_multiday_add_maps_to_date_range():
    resolution = parse_text_to_intent(
        "add HaNeul summer camp 14-07-2026 to 18-07-2026",
        commands.parse,
    )

    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.CREATE_EVENT
    assert resolution.intent.date_range is not None
    assert resolution.intent.date_range.start == date(2026, 7, 14)
    assert resolution.intent.date_range.end == date(2026, 7, 18)
    assert resolution.intent.metadata["all_day"] is True


def test_timed_multiday_add_maps_to_date_range_and_time_range():
    resolution = parse_text_to_intent(
        "add YounHa Cub Indoor Camp 17-04-2026 18:45 to 19-04-2026 16:00",
        commands.parse,
    )

    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.CREATE_EVENT
    assert resolution.intent.date_range is not None
    assert resolution.intent.date_range.start == date(2026, 4, 17)
    assert resolution.intent.date_range.end == date(2026, 4, 19)
    assert resolution.intent.time_range is not None
    assert resolution.intent.time_range.start == "18:45"
    assert resolution.intent.time_range.end == "16:00"
    assert resolution.intent.metadata["all_day"] is False


def test_edit_command_maps_to_update_intent():
    resolution = parse_text_to_intent(
        "edit SungHwan dentist time 15:00-16:00",
        commands.parse,
    )

    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.UPDATE_EVENT
    assert resolution.intent.target_calendar == "sunghwan"
    assert resolution.intent.title == "dentist"
    assert resolution.intent.changes == {"start": "15:00", "end": "16:00"}


def test_upcoming_command_maps_to_view_range_intent():
    resolution = parse_text_to_intent("upcoming Family 20", commands.parse)

    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.VIEW_RANGE
    assert resolution.intent.target_calendar == "family"
    assert resolution.intent.limit == 20
    assert resolution.intent.metadata["command"] == "upcoming"


def test_parse_error_becomes_invalid_resolution():
    resolution = command_to_intent({"error": "bad input"}, raw_input="bad input")

    assert resolution.status == ResolutionStatus.INVALID
    assert resolution.intent.action == IntentAction.HELP
    assert resolution.reason == "bad input"
