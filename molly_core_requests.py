"""
molly_core_requests.py — Structured request parsing for Molly Core bridges.

OpenClaw or other assistant layers should produce a compact JSON request. This
module validates that request at the boundary and converts it into Molly's
internal intent model before execution.
"""
from __future__ import annotations

from datetime import date

import config
from intent_models import (
    IntentAction,
    IntentResolution,
    IntentSource,
    ResolutionStatus,
    ScheduleIntent,
    TimeRange,
)


def resolution_from_request(payload: dict) -> IntentResolution:
    action = str(payload.get("action", "")).strip().lower()
    if action != "create_event":
        raise ValueError(
            "Unsupported action for Molly Core request interface: "
            f"{action or '<empty>'}"
        )

    calendar_key = _normalize_calendar(payload.get("target_calendar"))
    title = _required_string(payload.get("title"), "title")
    target_date = _parse_date(payload.get("target_date"))
    all_day = bool(payload.get("all_day", False))
    recurrence = _parse_recurrence(payload.get("recurrence"))

    time_range = None
    if not all_day:
        start_time = _required_string(payload.get("start_time"), "start_time")
        end_time = _required_string(payload.get("end_time"), "end_time")
        time_range = TimeRange(start=start_time, end=end_time)

    intent = ScheduleIntent(
        action=IntentAction.CREATE_EVENT,
        source=IntentSource.TELEGRAM_FREE_TEXT,
        raw_input=str(payload.get("raw_input", "")),
        target_calendar=calendar_key,
        title=title,
        target_date=target_date,
        time_range=time_range,
        recurrence=recurrence,
        metadata={
            "all_day": all_day,
            "nlu": str(payload.get("nlu", "openclaw")),
            "request_source": str(payload.get("request_source", "openclaw_bridge")),
        },
    )

    return IntentResolution(
        status=ResolutionStatus.READY,
        intent=intent,
    )


def _normalize_calendar(value) -> str:
    calendar = _required_string(value, "target_calendar").lower()
    if calendar not in config.CALENDARS:
        raise ValueError(f"Unknown target_calendar: {calendar}")
    return calendar


def _required_string(value, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"Missing required field: {field_name}")
    return text


def _parse_date(value) -> date:
    text = _required_string(value, "target_date")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Invalid target_date: {text}") from exc


def _parse_recurrence(value) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("recurrence must be a list of RRULE strings")
    return [str(item) for item in value]
