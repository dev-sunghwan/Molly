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


def resolution_from_request(payload: dict) -> IntentResolution:
    action = str(payload.get("action", "")).strip().lower()
    if action == "create_event":
        return _create_event_resolution(payload)
    if action == "view":
        return _view_resolution(payload)
    if action == "search":
        return _search_resolution(payload)
    if action == "delete_event":
        return _delete_event_resolution(payload)
    if action == "update_event":
        return _update_event_resolution(payload)
    raise ValueError(
        "Unsupported action for Molly Core request interface: "
        f"{action or '<empty>'}"
    )


def _create_event_resolution(payload: dict) -> IntentResolution:
    calendar_key = _normalize_calendar(payload.get("target_calendar"))
    title = _required_string(payload.get("title"), "title")
    target_date = _parse_date(payload.get("target_date"))
    end_date = _optional_date(payload.get("end_date"))
    all_day = bool(payload.get("all_day", False))
    recurrence = _parse_recurrence(payload.get("recurrence"))

    time_range = None
    if not all_day:
        start_time = _required_string(payload.get("start_time"), "start_time")
        end_time = _optional_string(payload.get("end_time"))
        if not end_time:
            parsed = utils.parse_time(start_time)
            if parsed is None:
                raise ValueError(f"Invalid start_time: {start_time}")
            _, end_time = parsed
        time_range = TimeRange(start=start_time, end=end_time)

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
        limit = int(payload.get("limit", 1 if scope == "next" else 10))
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
        changes["start"] = _required_string(changes_payload.get("start_time"), "changes.start_time")
        changes["end"] = _required_string(changes_payload.get("end_time"), "changes.end_time")
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
    calendar = _required_string(value, "target_calendar").lower()
    if calendar not in config.CALENDARS:
        raise ValueError(f"Unknown target_calendar: {calendar}")
    return calendar


def _optional_calendar(value) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return _normalize_calendar(value)


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
    return [str(item) for item in value]


def _optional_date(value) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    return _parse_date(value)
