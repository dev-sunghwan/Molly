"""
molly_core_requests.py — Structured request parsing for Molly Core bridges.

OpenClaw or other assistant layers should produce a compact JSON request. This
module validates that request at the boundary and converts it into Molly's
internal intent model before execution.
"""
from __future__ import annotations

from datetime import date, timedelta

import utils

import config
from intent_models import (
    DateRange,
    IntentAction,
    IntentResolution,
    IntentSource,
    ResolutionStatus,
    ScheduleIntent,
    TimeRange,
)


_COMMON_FIELDS = {
    "action",
    "request_id",
    "source",
    "source_message_id",
    "source_user_id",
    "source_user_name",
    "source_channel_id",
    "raw_input",
    "nlu",
    "request_source",
}

_ACTION_FIELDS = {
    "create_event": {
        "target_calendar",
        "title",
        "target_date",
        "end_date",
        "start_time",
        "end_time",
        "all_day",
        "recurrence",
    },
    "view": {"scope", "target_calendar", "target_date", "limit"},
    "search": {"query"},
    "delete_event": {"target_calendar", "title", "target_date"},
    "move_event": {"source_calendar", "target_calendar", "title", "target_date"},
    "update_event": {"target_calendar", "title", "target_date", "changes"},
}

_UPDATE_CHANGE_FIELDS = {"title", "target_date", "start_time", "end_time"}

_BLOCKED_FIELDS = {
    "code",
    "command",
    "db_write",
    "eval",
    "exec",
    "function_call",
    "python",
    "shell",
    "sql",
    "tool",
    "tool_call",
}


def resolution_from_request(payload: dict) -> IntentResolution:
    action = _validate_request_payload(payload)
    action = str(payload.get("action", "")).strip().lower()
    if action == "create_event":
        return _create_event_resolution(payload)
    if action == "view":
        return _view_resolution(payload)
    if action == "search":
        return _search_resolution(payload)
    if action == "delete_event":
        return _delete_event_resolution(payload)
    if action == "move_event":
        return _move_event_resolution(payload)
    if action == "update_event":
        return _update_event_resolution(payload)
    raise ValueError(
        "Unsupported action for Molly Core request interface: "
        f"{action or '<empty>'}"
    )


def _validate_request_payload(payload: dict) -> str:
    if not isinstance(payload, dict):
        raise ValueError("Molly Core request must be a JSON object")

    action = str(payload.get("action", "")).strip().lower()
    if action not in _ACTION_FIELDS:
        raise ValueError(
            "Unsupported action for Molly Core request interface: "
            f"{action or '<empty>'}"
        )

    allowed = _COMMON_FIELDS | _ACTION_FIELDS[action]
    unexpected = sorted(set(payload) - allowed)
    if unexpected:
        raise ValueError(f"Unsupported field(s) for {action}: {', '.join(unexpected)}")

    blocked = sorted(set(payload) & _BLOCKED_FIELDS)
    if blocked:
        raise ValueError(f"Unsafe field(s) are not allowed: {', '.join(blocked)}")

    if action == "update_event":
        changes = payload.get("changes")
        if isinstance(changes, dict):
            unexpected_changes = sorted(set(changes) - _UPDATE_CHANGE_FIELDS)
            if unexpected_changes:
                raise ValueError(
                    "Unsupported change field(s) for update_event: "
                    + ", ".join(unexpected_changes)
                )
            blocked_changes = sorted(set(changes) & _BLOCKED_FIELDS)
            if blocked_changes:
                raise ValueError(
                    "Unsafe change field(s) are not allowed: "
                    + ", ".join(blocked_changes)
                )

    return action


def _create_event_resolution(payload: dict) -> IntentResolution:
    calendar_key = _normalize_calendar(payload.get("target_calendar"))
    title = _required_string(payload.get("title"), "title")
    target_date = _parse_date(payload.get("target_date"))
    end_date = _optional_date(payload.get("end_date"))
    all_day = _optional_bool(payload.get("all_day"), default=False)
    recurrence = _parse_recurrence(payload.get("recurrence"))

    time_range = None
    if not all_day:
        start_time = _required_string(payload.get("start_time"), "start_time")
        start_time = _parse_clock_time(start_time, "start_time")
        end_time = _optional_string(payload.get("end_time"))
        if not end_time:
            parsed = utils.parse_time(start_time)
            if parsed is None:
                raise ValueError(f"Invalid start_time: {start_time}")
            _, end_time = parsed
        else:
            end_time = _parse_clock_time(end_time, "end_time")
        time_range = TimeRange(start=start_time, end=end_time)

    if recurrence and end_date is not None and end_date != target_date:
        raise ValueError(
            "Recurring events cannot use end_date as a series-until value. "
            "Use a single-day recurring seed event instead."
        )

    intent = ScheduleIntent(
        action=IntentAction.CREATE_EVENT,
        source=IntentSource.TELEGRAM_FREE_TEXT,
        raw_input=str(payload.get("raw_input", "")),
        target_calendar=calendar_key,
        title=title,
        target_date=target_date,
        date_range=DateRange(start=target_date, end=end_date) if end_date is not None else None,
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


def _view_resolution(payload: dict) -> IntentResolution:
    scope = _required_string(payload.get("scope"), "scope").lower()
    calendar_key = _optional_calendar(payload.get("target_calendar"))
    raw_input = str(payload.get("raw_input", ""))

    if scope in {"today", "tomorrow"}:
        metadata = {"command": "today" if scope == "today" else "tomorrow"}
        target_date = None if scope == "today" else (date.today() + timedelta(days=1))
        intent = ScheduleIntent(
            action=IntentAction.VIEW_DAILY,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input=raw_input,
            target_calendar=calendar_key,
            target_date=target_date,
            metadata=metadata,
        )
        return IntentResolution(status=ResolutionStatus.READY, intent=intent)

    if scope in {"next", "upcoming"}:
        limit = _optional_limit(payload.get("limit"), default=1 if scope == "next" else 10)
        metadata = {"command": "next" if scope == "next" else "upcoming"}
        intent = ScheduleIntent(
            action=IntentAction.VIEW_RANGE,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input=raw_input,
            target_calendar=calendar_key,
            limit=limit,
            metadata=metadata,
        )
        return IntentResolution(status=ResolutionStatus.READY, intent=intent)

    if scope in {"week", "week_next", "month", "month_remaining", "month_next"}:
        intent = ScheduleIntent(
            action=IntentAction.VIEW_RANGE,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input=raw_input,
            target_calendar=calendar_key,
            metadata={"command": scope},
        )
        return IntentResolution(status=ResolutionStatus.READY, intent=intent)

    if scope == "date":
        target_date = _parse_date(payload.get("target_date"))
        intent = ScheduleIntent(
            action=IntentAction.VIEW_DAILY,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input=raw_input,
            target_calendar=calendar_key,
            target_date=target_date,
            metadata={"command": "date"},
        )
        return IntentResolution(status=ResolutionStatus.READY, intent=intent)

    raise ValueError(f"Unsupported view scope: {scope}")


def _search_resolution(payload: dict) -> IntentResolution:
    query = _required_string(payload.get("query"), "query")
    intent = ScheduleIntent(
        action=IntentAction.SEARCH,
        source=IntentSource.TELEGRAM_FREE_TEXT,
        raw_input=str(payload.get("raw_input", query)),
        search_query=query,
    )
    return IntentResolution(status=ResolutionStatus.READY, intent=intent)


def _delete_event_resolution(payload: dict) -> IntentResolution:
    intent = ScheduleIntent(
        action=IntentAction.DELETE_EVENT,
        source=IntentSource.TELEGRAM_FREE_TEXT,
        raw_input=str(payload.get("raw_input", "")),
        target_calendar=_normalize_calendar(payload.get("target_calendar")),
        title=_required_string(payload.get("title"), "title"),
        target_date=_optional_date(payload.get("target_date")),
    )
    return IntentResolution(status=ResolutionStatus.READY, intent=intent)




def _move_event_resolution(payload: dict) -> IntentResolution:
    intent = ScheduleIntent(
        action=IntentAction.MOVE_EVENT,
        source=IntentSource.TELEGRAM_FREE_TEXT,
        raw_input=str(payload.get("raw_input", "")),
        source_calendar=_normalize_calendar(payload.get("source_calendar")),
        target_calendar=_normalize_calendar(payload.get("target_calendar")),
        title=_required_string(payload.get("title"), "title"),
        target_date=_optional_date(payload.get("target_date")),
    )
    return IntentResolution(status=ResolutionStatus.READY, intent=intent)

def _update_event_resolution(payload: dict) -> IntentResolution:
    changes_payload = payload.get("changes")
    if not isinstance(changes_payload, dict):
        raise ValueError("changes must be an object for update_event")

    changes: dict[str, object] = {}
    if "title" in changes_payload:
        changes["title"] = _required_string(changes_payload.get("title"), "changes.title")
    if "target_date" in changes_payload:
        changes["date"] = _parse_date(changes_payload.get("target_date"))
    has_start = "start_time" in changes_payload
    has_end = "end_time" in changes_payload
    if has_start != has_end:
        raise ValueError("changes.start_time and changes.end_time must be provided together")
    if has_start and has_end:
        changes["start"] = _parse_clock_time(
            _required_string(changes_payload.get("start_time"), "changes.start_time"),
            "changes.start_time",
        )
        changes["end"] = _parse_clock_time(
            _required_string(changes_payload.get("end_time"), "changes.end_time"),
            "changes.end_time",
        )
    if not changes:
        raise ValueError("update_event requires at least one change")

    intent = ScheduleIntent(
        action=IntentAction.UPDATE_EVENT,
        source=IntentSource.TELEGRAM_FREE_TEXT,
        raw_input=str(payload.get("raw_input", "")),
        target_calendar=_normalize_calendar(payload.get("target_calendar")),
        title=_required_string(payload.get("title"), "title"),
        target_date=_optional_date(payload.get("target_date")),
        changes=changes,
    )
    return IntentResolution(status=ResolutionStatus.READY, intent=intent)


def _normalize_calendar(value) -> str:
    raw = _required_string(value, "target_calendar")
    calendar = config.normalize_calendar_name(raw)
    if calendar is None:
        raise ValueError(f"Unknown target_calendar: {raw}")
    return calendar


def _optional_calendar(value) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    raw = str(value).strip()
    calendar = config.normalize_calendar_name(raw)
    if calendar is None:
        raise ValueError(f"Unknown target_calendar: {raw}")
    return calendar


def _required_string(value, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"Missing required field: {field_name}")
    return text


def _optional_string(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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
    recurrence = [str(item).strip() for item in value]
    for item in recurrence:
        if not item.startswith("RRULE:"):
            raise ValueError(f"Unsupported recurrence item: {item}")
    return recurrence


def _optional_date(value) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    return _parse_date(value)


def _optional_bool(value, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ValueError("all_day must be a boolean")


def _parse_clock_time(value: str, field_name: str) -> str:
    parsed = utils.parse_clock_time(value)
    if parsed is None:
        raise ValueError(f"Invalid {field_name}: {value}")
    return parsed


def _optional_limit(value, *, default: int) -> int:
    if value is None:
        return default
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid limit: {value}") from exc
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    return limit
