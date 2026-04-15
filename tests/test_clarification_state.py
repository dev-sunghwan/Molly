from datetime import date

import clarification_state
from intent_adapter import parse_text_to_intent
from intent_models import IntentAction, ResolutionStatus


def setup_function():
    clarification_state.clear_pending(123)


def test_missing_calendar_add_creates_clarification_resolution():
    resolution = parse_text_to_intent("add tennis tomorrow 17:00-18:00", lambda text: {"error": "bad"})

    assert resolution.status == ResolutionStatus.NEEDS_CLARIFICATION
    assert resolution.intent.action == IntentAction.CREATE_EVENT
    assert resolution.intent.title == "tennis"
    assert resolution.intent.target_date is not None
    assert resolution.intent.time_range is not None
    assert resolution.missing_fields == ["target_calendar"]


def test_pending_clarification_accepts_calendar_reply():
    resolution = parse_text_to_intent("add tennis 15-04-2026 17:00-18:00", lambda text: {"error": "bad"})
    clarification_state.set_pending(123, resolution)

    updated = clarification_state.apply_reply(123, "YounHa")

    assert updated is not None
    assert updated.status == ResolutionStatus.READY
    assert updated.intent.target_calendar == "younha"
    assert updated.intent.title == "tennis"
    assert updated.intent.target_date == date(2026, 4, 15)


def test_unusable_reply_keeps_pending_state():
    resolution = parse_text_to_intent("add tennis tomorrow 17:00-18:00", lambda text: {"error": "bad"})
    clarification_state.set_pending(123, resolution)

    updated = clarification_state.apply_reply(123, "maybe later")

    assert updated is None
    assert clarification_state.get_pending(123) is not None
