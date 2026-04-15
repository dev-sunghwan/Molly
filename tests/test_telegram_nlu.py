from datetime import timedelta

import clarification_state
from telegram_extraction import ExtractedTelegramDraft
import telegram_nlu
import utils
from intent_models import IntentAction, ResolutionStatus


def setup_function():
    clarification_state.clear_pending(999)


def test_korean_view_today_request():
    resolution = telegram_nlu.parse_free_text_to_intent("오늘 일정 보여줘")

    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.VIEW_DAILY
    assert resolution.intent.metadata["command"] == "today"


def test_korean_create_request_ready():
    resolution = telegram_nlu.parse_free_text_to_intent("내일 오후 5시에 윤하 테니스 넣어줘")

    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.CREATE_EVENT
    assert resolution.intent.target_calendar == "younha"
    assert resolution.intent.title == "테니스"
    assert resolution.intent.target_date == utils._today_local() + timedelta(days=1)
    assert resolution.intent.time_range is not None
    assert resolution.intent.time_range.start == "17:00"


def test_korean_create_request_needs_calendar_clarification():
    resolution = telegram_nlu.parse_free_text_to_intent("내일 오후 5시에 테니스 넣어줘")

    assert resolution is not None
    assert resolution.status == ResolutionStatus.NEEDS_CLARIFICATION
    assert "target_calendar" in resolution.missing_fields


def test_korean_create_request_needs_date_clarification():
    resolution = telegram_nlu.parse_free_text_to_intent("윤하 테니스 넣어줘")

    assert resolution is not None
    assert resolution.status == ResolutionStatus.NEEDS_CLARIFICATION
    assert "target_date" in resolution.missing_fields


def test_clarification_state_can_fill_target_date():
    resolution = telegram_nlu.parse_free_text_to_intent("윤하 테니스 넣어줘")
    clarification_state.set_pending(999, resolution)

    updated = clarification_state.apply_reply(999, "tomorrow")

    assert updated is not None
    assert updated.status == ResolutionStatus.READY
    assert updated.intent.target_calendar == "younha"
    assert updated.intent.target_date == utils._today_local() + timedelta(days=1)


def test_structured_draft_can_drive_create_event():
    draft = ExtractedTelegramDraft(
        action="create_event",
        target_calendar="윤하",
        title="테니스",
        target_date_text="내일",
        time_text="오후 5시",
        confidence=0.95,
    )

    resolution = telegram_nlu.parse_free_text_to_intent(
        "내일 오후에 윤하 테니스 넣어줘",
        extracted_draft=draft,
    )

    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.CREATE_EVENT
    assert resolution.intent.target_calendar == "younha"
    assert resolution.intent.title == "테니스"
    assert resolution.intent.target_date == utils._today_local() + timedelta(days=1)
    assert resolution.intent.time_range is not None
    assert resolution.intent.time_range.start == "17:00"
    assert resolution.intent.metadata["nlu"] == "telegram_llm"


def test_structured_draft_can_request_clarification():
    draft = ExtractedTelegramDraft(
        action="create_event",
        title="테니스",
        target_date_text="내일",
        missing_fields=["target_calendar"],
        confidence=0.62,
    )

    resolution = telegram_nlu.parse_free_text_to_intent(
        "내일 테니스 넣어줘",
        extracted_draft=draft,
    )

    assert resolution is not None
    assert resolution.status == ResolutionStatus.NEEDS_CLARIFICATION
    assert "target_calendar" in resolution.missing_fields


def test_structured_draft_can_drive_view_range():
    draft = ExtractedTelegramDraft(
        action="view_range",
        target_date_text="다음주",
        confidence=0.9,
    )

    resolution = telegram_nlu.parse_free_text_to_intent(
        "다음주 일정 보여줘",
        extracted_draft=draft,
    )

    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.VIEW_RANGE
    assert resolution.intent.metadata["command"] == "week_next"
