"""
telegram_nlu.py — Hybrid natural-language interpretation for Telegram.

This module supports a safe hybrid path for day-to-day Telegram scheduling:
- first choice: a structured LLM/OpenClaw draft when one is supplied
- fallback: lightweight Korean/English heuristics
- deterministic clarification when key fields are still missing
"""
from __future__ import annotations

import re
from datetime import timedelta

import config
from telegram_extraction import ExtractedTelegramDraft, build_extraction_prompt
import utils
from intent_models import IntentAction, IntentResolution, IntentSource, ResolutionStatus, ScheduleIntent, TimeRange



def parse_free_text_to_intent(
    text: str,
    extracted_draft: ExtractedTelegramDraft | None = None,
) -> IntentResolution | None:
    stripped = text.strip()
    if not stripped:
        return None

    if extracted_draft is not None:
        draft_resolution = _resolution_from_draft(stripped, extracted_draft)
        if draft_resolution is not None:
            return draft_resolution

    lowered = stripped.lower()

    view_resolution = _parse_view_request(stripped, lowered)
    if view_resolution is not None:
        return view_resolution

    create_resolution = _parse_create_request(stripped, lowered)
    if create_resolution is not None:
        return create_resolution

    return None


def build_free_text_extraction_prompt(text: str) -> str:
    return build_extraction_prompt(text)


def _resolution_from_draft(
    text: str,
    draft: ExtractedTelegramDraft,
) -> IntentResolution | None:
    action = (draft.action or "").strip().lower()
    if not action:
        return None

    if action == "create_event":
        calendar = _normalize_calendar(draft.target_calendar)
        target_date = _extract_relative_date(
            draft.target_date_text or "",
            (draft.target_date_text or "").lower(),
        )
        time_range = _extract_natural_time(draft.time_text or "") if draft.time_text else None
        title = (draft.title or "").strip() or None

        intent = ScheduleIntent(
            action=IntentAction.CREATE_EVENT,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input=text,
            target_calendar=calendar,
            title=title,
            target_date=target_date,
            time_range=time_range,
            metadata={
                "all_day": time_range is None,
                "nlu": "telegram_llm",
                "draft_confidence": draft.confidence,
                "draft_reasoning": draft.reasoning,
            },
        )
        missing = _missing_fields_for_create(intent, draft.missing_fields)
        if missing:
            return IntentResolution(
                status=ResolutionStatus.NEEDS_CLARIFICATION,
                intent=intent,
                missing_fields=missing,
                clarification_prompt=_clarification_prompt(missing),
                reason=draft.reasoning,
            )
        return _ready(intent)

    if action == "view_daily":
        target_date = _extract_relative_date(
            draft.target_date_text or "",
            (draft.target_date_text or "").lower(),
        )
        if target_date is None:
            return IntentResolution(
                status=ResolutionStatus.NEEDS_CLARIFICATION,
                intent=ScheduleIntent(
                    action=IntentAction.VIEW_DAILY,
                    source=IntentSource.TELEGRAM_FREE_TEXT,
                    raw_input=text,
                    metadata={"nlu": "telegram_llm"},
                ),
                missing_fields=["target_date"],
                clarification_prompt=_clarification_prompt(["target_date"]),
                reason=draft.reasoning,
            )
        return _ready(
            ScheduleIntent(
                action=IntentAction.VIEW_DAILY,
                source=IntentSource.TELEGRAM_FREE_TEXT,
                raw_input=text,
                target_date=target_date,
                metadata={"command": "date", "nlu": "telegram_llm"},
            )
        )

    if action == "view_range":
        command = _normalize_range_command(draft.target_date_text or "")
        if command is None:
            return None
        return _ready(
            ScheduleIntent(
                action=IntentAction.VIEW_RANGE,
                source=IntentSource.TELEGRAM_FREE_TEXT,
                raw_input=text,
                metadata={"command": command, "nlu": "telegram_llm"},
                limit=draft.limit,
            )
        )

    return None


def _parse_view_request(text: str, lowered: str) -> IntentResolution | None:
    if any(phrase in text for phrase in ["오늘 일정", "오늘 스케줄"]) or any(
        phrase in lowered for phrase in ["today schedule", "today calendar", "what's on today"]
    ):
        return _ready(
            ScheduleIntent(
                action=IntentAction.VIEW_DAILY,
                source=IntentSource.TELEGRAM_FREE_TEXT,
                raw_input=text,
                metadata={"command": "today", "nlu": "telegram"},
            )
        )

    if any(phrase in text for phrase in ["내일 일정", "내일 스케줄"]) or any(
        phrase in lowered for phrase in ["tomorrow schedule", "tomorrow calendar", "what's on tomorrow"]
    ):
        return _ready(
            ScheduleIntent(
                action=IntentAction.VIEW_DAILY,
                source=IntentSource.TELEGRAM_FREE_TEXT,
                raw_input=text,
                metadata={"command": "tomorrow", "nlu": "telegram"},
            )
        )

    if any(phrase in text for phrase in ["이번주 일정", "이번 주 일정", "이번주 스케줄"]) or any(
        phrase in lowered for phrase in ["this week schedule", "this week calendar"]
    ):
        return _ready(
            ScheduleIntent(
                action=IntentAction.VIEW_RANGE,
                source=IntentSource.TELEGRAM_FREE_TEXT,
                raw_input=text,
                metadata={"command": "week", "nlu": "telegram"},
            )
        )

    if any(phrase in text for phrase in ["다음주 일정", "다음 주 일정", "다음주 스케줄"]) or any(
        phrase in lowered for phrase in ["next week schedule", "next week calendar"]
    ):
        return _ready(
            ScheduleIntent(
                action=IntentAction.VIEW_RANGE,
                source=IntentSource.TELEGRAM_FREE_TEXT,
                raw_input=text,
                metadata={"command": "week_next", "nlu": "telegram"},
            )
        )

    if any(phrase in text for phrase in ["이번달 일정", "이번 달 일정", "이번달 스케줄"]) or any(
        phrase in lowered for phrase in ["this month schedule", "this month calendar"]
    ):
        return _ready(
            ScheduleIntent(
                action=IntentAction.VIEW_RANGE,
                source=IntentSource.TELEGRAM_FREE_TEXT,
                raw_input=text,
                metadata={"command": "month", "nlu": "telegram"},
            )
        )

    if any(phrase in text for phrase in ["다음달 일정", "다음 달 일정", "다음달 스케줄"]) or any(
        phrase in lowered for phrase in ["next month schedule", "next month calendar"]
    ):
        return _ready(
            ScheduleIntent(
                action=IntentAction.VIEW_RANGE,
                source=IntentSource.TELEGRAM_FREE_TEXT,
                raw_input=text,
                metadata={"command": "month_next", "nlu": "telegram"},
            )
        )

    return None


def _parse_create_request(text: str, lowered: str) -> IntentResolution | None:
    if not _looks_like_create_request(text, lowered):
        return None

    calendar = _extract_calendar_alias(lowered)
    target_date = _extract_relative_date(text, lowered)
    time_range = _extract_natural_time(text)
    title = _extract_title(text, lowered, calendar)

    intent = ScheduleIntent(
        action=IntentAction.CREATE_EVENT,
        source=IntentSource.TELEGRAM_FREE_TEXT,
        raw_input=text,
        target_calendar=calendar,
        title=title,
        target_date=target_date,
        time_range=time_range,
        metadata={"all_day": time_range is None, "nlu": "telegram"},
    )

    missing = _missing_fields_for_create(intent, [])

    if missing:
        return IntentResolution(
            status=ResolutionStatus.NEEDS_CLARIFICATION,
            intent=intent,
            missing_fields=missing,
            clarification_prompt=_clarification_prompt(missing),
        )

    return _ready(intent)


def _looks_like_create_request(text: str, lowered: str) -> bool:
    markers = [
        "추가",
        "넣어",
        "넣어줘",
        "등록",
        "등록해",
        "잡아",
        "잡아줘",
        "예약",
        "schedule",
        "add ",
        "book ",
        "put ",
    ]
    return any(marker in text or marker in lowered for marker in markers)


def _extract_calendar_alias(lowered: str) -> str | None:
    for calendar, aliases in config.CALENDAR_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return calendar
    for calendar in config.CALENDARS:
        if calendar in lowered:
            return calendar
    return None


def _normalize_calendar(value: str | None) -> str | None:
    return config.normalize_calendar_name(value)


def _extract_relative_date(text: str, lowered: str):
    if "오늘" in text:
        return utils._today_local()
    if "내일" in text:
        return utils._today_local() + timedelta(days=1)
    if "모레" in text:
        return utils._today_local() + timedelta(days=2)

    english_tokens = lowered.replace(",", " ").split()
    for token in english_tokens:
        parsed = utils.parse_date(token)
        if parsed is not None:
            return parsed

    korean_weekdays = {
        "월요일": "mon",
        "화요일": "tue",
        "수요일": "wed",
        "목요일": "thu",
        "금요일": "fri",
        "토요일": "sat",
        "일요일": "sun",
    }
    for korean, english in korean_weekdays.items():
        if korean in text:
            return utils.parse_date(english)

    return None


def _normalize_range_command(value: str) -> str | None:
    lowered = value.strip().lower()
    if not lowered:
        return None

    mapping = {
        "today": "today",
        "tomorrow": "tomorrow",
        "this week": "week",
        "next week": "week_next",
        "this month": "month",
        "next month": "month_next",
        "오늘": "today",
        "내일": "tomorrow",
        "이번주": "week",
        "이번 주": "week",
        "다음주": "week_next",
        "다음 주": "week_next",
        "이번달": "month",
        "이번 달": "month",
        "다음달": "month_next",
        "다음 달": "month_next",
    }
    return mapping.get(lowered)


def _extract_natural_time(text: str) -> TimeRange | None:
    hhmm_match = re.search(r"\b(\d{1,2}:\d{2}(?:-\d{1,2}:\d{2})?)\b", text)
    if hhmm_match:
        parsed = utils.parse_time(hhmm_match.group(1))
        if parsed is not None:
            return TimeRange(start=parsed[0], end=parsed[1])

    ampm_match = re.search(r"(오전|오후)\s*(\d{1,2})(?:시)?(?:\s*(\d{1,2})분?)?", text)
    if ampm_match:
        period, hour_text, minute_text = ampm_match.groups()
        hour = int(hour_text)
        minute = int(minute_text or 0)
        if period == "오후" and hour != 12:
            hour += 12
        if period == "오전" and hour == 12:
            hour = 0
        parsed = utils.parse_time(f"{hour:02d}:{minute:02d}")
        if parsed is not None:
            return TimeRange(start=parsed[0], end=parsed[1])

    korean_hour_match = re.search(r"\b(\d{1,2})시(?:\s*(\d{1,2})분?)?", text)
    if korean_hour_match:
        hour = int(korean_hour_match.group(1))
        minute = int(korean_hour_match.group(2) or 0)
        parsed = utils.parse_time(f"{hour:02d}:{minute:02d}")
        if parsed is not None:
            return TimeRange(start=parsed[0], end=parsed[1])

    english_ampm_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text.lower())
    if english_ampm_match:
        hour = int(english_ampm_match.group(1))
        minute = int(english_ampm_match.group(2) or 0)
        period = english_ampm_match.group(3)
        if period == "pm" and hour != 12:
            hour += 12
        if period == "am" and hour == 12:
            hour = 0
        parsed = utils.parse_time(f"{hour:02d}:{minute:02d}")
        if parsed is not None:
            return TimeRange(start=parsed[0], end=parsed[1])

    return None


def _extract_title(text: str, lowered: str, calendar: str | None) -> str | None:
    title = text

    removable_phrases = [
        "오늘",
        "내일",
        "모레",
        "일정",
        "스케줄",
        "추가해줘",
        "추가해",
        "추가",
        "넣어줘",
        "넣어",
        "등록해줘",
        "등록해",
        "등록",
        "잡아줘",
        "잡아",
        "예약해줘",
        "예약",
        "please",
        "schedule",
        "add",
        "for",
        "on",
        "at",
    ]
    for phrase in removable_phrases:
        title = re.sub(re.escape(phrase), " ", title, flags=re.IGNORECASE)

    if calendar is not None:
        for alias in config.CALENDAR_ALIASES.get(calendar, []):
            title = re.sub(re.escape(alias), " ", title, flags=re.IGNORECASE)

    title = re.sub(r"\b\d{1,2}:\d{2}(?:-\d{1,2}:\d{2})?\b", " ", title)
    title = re.sub(r"(오전|오후)\s*\d{1,2}(?:시)?(?:\s*\d{1,2}분?)?", " ", title)
    title = re.sub(r"\b\d{1,2}시(?:\s*\d{1,2}분?)?(?:에)?", " ", title)
    title = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(am|pm)\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"(월요일|화요일|수요일|목요일|금요일|토요일|일요일)", " ", title)
    title = re.sub(r"\b에\b", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" ,.")
    return title or None


def _clarification_prompt(missing_fields: list[str]) -> str:
    if missing_fields == ["target_calendar"]:
        return "어느 가족 캘린더에 넣을까요? (Which family calendar should Molly use?)"
    if missing_fields == ["target_date"]:
        return "어떤 날짜로 넣을까요? (What date should Molly use?)"
    if "target_calendar" in missing_fields and "target_date" in missing_fields:
        return "누구 일정인지와 날짜를 알려주세요. (Tell Molly the calendar and date.)"
    if "title" in missing_fields:
        return "일정 제목을 조금 더 구체적으로 알려주세요. (Please clarify the event title.)"
    return "Molly needs a bit more information before it can continue."


def _ready(intent: ScheduleIntent) -> IntentResolution:
    return IntentResolution(status=ResolutionStatus.READY, intent=intent)


def _missing_fields_for_create(intent: ScheduleIntent, additional_missing: list[str]) -> list[str]:
    missing = list(additional_missing)
    if not intent.target_calendar and "target_calendar" not in missing:
        missing.append("target_calendar")
    if not intent.title and "title" not in missing:
        missing.append("title")
    if intent.target_date is None and "target_date" not in missing:
        missing.append("target_date")
    return missing
