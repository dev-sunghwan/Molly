"""
clarification_state.py — Pending clarification state backed by SQLite.
"""
from __future__ import annotations

from dataclasses import dataclass

import config
import state_store
from intent_adapter import validate_intent
from intent_models import IntentResolution, ScheduleIntent, TimeRange
import utils


@dataclass
class PendingClarification:
    user_id: int
    resolution: IntentResolution


def set_pending(user_id: int, resolution: IntentResolution) -> None:
    state_store.save_pending_clarification(user_id, resolution)


def get_pending(user_id: int) -> PendingClarification | None:
    resolution = state_store.load_pending_clarification(user_id)
    if resolution is None:
        return None
    return PendingClarification(user_id=user_id, resolution=resolution)


def clear_pending(user_id: int) -> None:
    state_store.clear_pending_clarification(user_id)


def apply_reply(user_id: int, text: str) -> IntentResolution | None:
    """
    Apply a user's clarification reply to a pending intent if possible.
    Returns:
      - updated resolution when the reply is understood
      - None when there is no pending clarification or the reply cannot be used
    """
    pending = get_pending(user_id)
    if pending is None:
        return None

    resolution = pending.resolution
    intent = resolution.intent
    reply = text.strip().lower()

    if "target_calendar" in resolution.missing_fields and reply in config.CALENDARS:
        updated_intent = _copy_intent(intent)
        updated_intent.target_calendar = reply
        updated_resolution = validate_intent(updated_intent)
        if updated_resolution.status == updated_resolution.status.READY:
            clear_pending(user_id)
        else:
            set_pending(user_id, updated_resolution)
        return updated_resolution

    if "target_date" in resolution.missing_fields:
        parsed_date = utils.parse_date(reply)
        if parsed_date is not None:
            updated_intent = _copy_intent(intent)
            updated_intent.target_date = parsed_date
            remaining_missing = [field for field in resolution.missing_fields if field != "target_date"]
            if remaining_missing:
                updated_resolution = IntentResolution(
                    status=resolution.status,
                    intent=updated_intent,
                    missing_fields=remaining_missing,
                    clarification_prompt=_clarification_prompt(remaining_missing),
                )
                set_pending(user_id, updated_resolution)
                return updated_resolution

            updated_resolution = validate_intent(updated_intent)
            clear_pending(user_id)
            return updated_resolution

    if "time_range" in resolution.missing_fields:
        parsed_time = utils.parse_time(reply)
        if parsed_time is not None:
            updated_intent = _copy_intent(intent)
            updated_intent.time_range = TimeRange(start=parsed_time[0], end=parsed_time[1])
            remaining_missing = [field for field in resolution.missing_fields if field != "time_range"]
            if remaining_missing:
                updated_resolution = IntentResolution(
                    status=resolution.status,
                    intent=updated_intent,
                    missing_fields=remaining_missing,
                    clarification_prompt=_clarification_prompt(remaining_missing),
                )
                set_pending(user_id, updated_resolution)
                return updated_resolution

            updated_resolution = validate_intent(updated_intent)
            clear_pending(user_id)
            return updated_resolution

    return None


def _copy_intent(intent: ScheduleIntent) -> ScheduleIntent:
    return ScheduleIntent(
        action=intent.action,
        source=intent.source,
        raw_input=intent.raw_input,
        target_calendar=intent.target_calendar,
        title=intent.title,
        target_date=intent.target_date,
        date_range=intent.date_range,
        time_range=intent.time_range,
        recurrence=list(intent.recurrence),
        search_query=intent.search_query,
        help_topic=intent.help_topic,
        limit=intent.limit,
        changes=dict(intent.changes),
        metadata=dict(intent.metadata),
    )


def _clarification_prompt(missing_fields: list[str]) -> str:
    if missing_fields == ["target_calendar"]:
        return "어느 가족 캘린더에 넣을까요? (Which family calendar should Molly use?)"
    if missing_fields == ["target_date"]:
        return "어떤 날짜로 넣을까요? (What date should Molly use?)"
    if missing_fields == ["time_range"]:
        return "몇 시로 넣을까요? 시작 시간을 알려주세요. (What time should Molly use?)"
    if "target_calendar" in missing_fields and "target_date" in missing_fields:
        return "누구 일정인지와 날짜를 알려주세요. (Tell Molly the calendar and date.)"
    if "target_calendar" in missing_fields and "time_range" in missing_fields:
        return "누구 일정인지와 시간을 알려주세요. (Tell Molly the calendar and time.)"
    if "target_date" in missing_fields and "time_range" in missing_fields:
        return "날짜와 시간을 알려주세요. (Tell Molly the date and time.)"
    return "Molly needs more information before it can continue."
