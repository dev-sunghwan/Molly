from datetime import date, timedelta
import calendar

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


def test_korean_create_request_needs_time_clarification():
    resolution = telegram_nlu.parse_free_text_to_intent("내일 윤하 테니스 넣어줘")

    assert resolution is not None
    assert resolution.status == ResolutionStatus.NEEDS_CLARIFICATION
    assert "time_range" in resolution.missing_fields


def test_clarification_state_can_fill_time_range():
    resolution = telegram_nlu.parse_free_text_to_intent("내일 윤하 테니스 넣어줘")
    clarification_state.set_pending(999, resolution)

    updated = clarification_state.apply_reply(999, "17:00")

    assert updated is not None
    assert updated.status == ResolutionStatus.READY
    assert updated.intent.time_range is not None
    assert updated.intent.time_range.start == "17:00"
    assert updated.intent.time_range.end == "18:00"


def test_clarification_state_can_fill_target_date():
    resolution = telegram_nlu.parse_free_text_to_intent("윤하 테니스 넣어줘")
    clarification_state.set_pending(999, resolution)

    updated = clarification_state.apply_reply(999, "tomorrow")

    assert updated is not None
    assert updated.status == ResolutionStatus.NEEDS_CLARIFICATION
    assert updated.intent.target_calendar == "younha"
    assert updated.intent.target_date == utils._today_local() + timedelta(days=1)
    assert "time_range" in updated.missing_fields


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




def test_korean_remaining_month_view_request_maps_to_remaining_month():
    resolution = telegram_nlu.parse_free_text_to_intent("이번 달 남은 일정 보여줘")

    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.VIEW_RANGE
    assert resolution.intent.metadata["command"] == "month_remaining"


def test_structured_draft_with_remaining_month_maps_to_remaining_month():
    draft = ExtractedTelegramDraft(
        action="view_range",
        target_date_text="이번 달 남은",
        confidence=0.9,
    )

    resolution = telegram_nlu.parse_free_text_to_intent(
        "이번 달 남은 일정 보여줘",
        extracted_draft=draft,
    )

    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.metadata["command"] == "month_remaining"


def test_english_month_name_view_request_maps_to_current_month_when_same_month():
    month_name = calendar.month_name[utils._today_local().month]
    resolution = telegram_nlu.parse_free_text_to_intent(f"Show me {month_name} schedule")

    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.VIEW_RANGE
    assert resolution.intent.metadata["command"] == "month"


def test_english_month_name_view_request_maps_to_explicit_future_month():
    resolution = telegram_nlu.parse_free_text_to_intent("Show me July schedule")

    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.VIEW_RANGE
    assert resolution.intent.metadata["command"] == "month:2026-07"


def test_structured_draft_with_month_name_maps_to_current_month_when_same_month():
    month_name = calendar.month_name[utils._today_local().month]
    draft = ExtractedTelegramDraft(
        action="view_range",
        target_date_text=month_name,
        confidence=0.9,
    )

    resolution = telegram_nlu.parse_free_text_to_intent(
        f"Show me {month_name} schedule",
        extracted_draft=draft,
    )

    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.metadata["command"] == "month"


def test_structured_draft_with_month_name_maps_to_explicit_future_month():
    draft = ExtractedTelegramDraft(
        action="view_range",
        target_date_text="July",
        confidence=0.9,
    )

    resolution = telegram_nlu.parse_free_text_to_intent(
        "Show me July schedule",
        extracted_draft=draft,
    )

    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.metadata["command"] == "month:2026-07"


def test_korean_month_number_view_request_maps_to_explicit_month():
    resolution = telegram_nlu.parse_free_text_to_intent("7월 일정 보여줘")

    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.VIEW_RANGE
    assert resolution.intent.metadata["command"] == "month:2026-07"


def test_structured_draft_with_korean_month_number_maps_to_explicit_month():
    draft = ExtractedTelegramDraft(
        action="view_range",
        target_date_text="7월",
        confidence=0.9,
    )

    resolution = telegram_nlu.parse_free_text_to_intent(
        "7월 일정 보여줘",
        extracted_draft=draft,
    )

    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.metadata["command"] == "month:2026-07"


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


def test_structured_draft_can_drive_update_event():
    draft = ExtractedTelegramDraft(
        action="update_event",
        target_calendar="지영",
        title="running",
        target_date_text="내일",
        time_text="오후 8시 15분부터 9시",
        confidence=0.94,
    )

    resolution = telegram_nlu.parse_free_text_to_intent(
        "지영 running 내일 시간을 오후 8시 15분부터 9시로 바꿔줘",
        extracted_draft=draft,
    )

    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY
    assert resolution.intent.action == IntentAction.UPDATE_EVENT
    assert resolution.intent.target_calendar == "jeeyoung"
    assert resolution.intent.title == "running"
    assert resolution.intent.target_date == utils._today_local() + timedelta(days=1)
    assert resolution.intent.changes["start"] == "20:15"
    assert resolution.intent.changes["end"] == "21:15"
    assert resolution.intent.metadata["nlu"] == "telegram_llm"


def test_structured_draft_update_event_can_request_clarification():
    draft = ExtractedTelegramDraft(
        action="update_event",
        title="running",
        confidence=0.61,
        missing_fields=["target_calendar", "changes"],
    )

    resolution = telegram_nlu.parse_free_text_to_intent(
        "running 바꿔줘",
        extracted_draft=draft,
    )

    assert resolution is not None
    assert resolution.status == ResolutionStatus.NEEDS_CLARIFICATION
    assert "target_calendar" in resolution.missing_fields
    assert "changes" in resolution.missing_fields
