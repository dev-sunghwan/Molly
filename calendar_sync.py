"""
Stage-1 local-to-Google calendar sync helpers.

This sync is intentionally conservative.
- Local calendar remains the source of truth.
- Google Calendar is treated as an optional mirror/export target.
- Only missing events are inserted.
- Existing Google events are never edited or deleted in this stage.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import config
import google_calendar_backend
import local_calendar_backend
import utils


@dataclass
class SyncSummary:
    inserted: int = 0
    skipped_existing: int = 0
    skipped_unsupported: int = 0


@dataclass
class LocalEventForSync:
    calendar_key: str
    summary: str
    start_date: date
    end_date: date
    start_time: str | None
    end_time: str | None
    all_day: bool
    recurrence: list[str]


def sync_local_to_google(
    start_date: date,
    end_date: date,
    *,
    dry_run: bool = True,
    calendar_keys: list[str] | None = None,
) -> tuple[SyncSummary, list[str]]:
    local_service = local_calendar_backend.authenticate()
    google_service = google_calendar_backend.authenticate()

    selected = set(calendar_keys or config.CALENDARS.keys())
    google_events_by_calendar = {
        calendar_key: google_calendar_backend.list_events_range(google_service, start_date, end_date)
        for calendar_key in selected
    }

    summary = SyncSummary()
    details: list[str] = []

    for event in _iter_local_events(local_service, start_date, end_date, selected):
        if event.recurrence and not _is_supported_recurrence(event.recurrence):
            summary.skipped_unsupported += 1
            details.append(f"SKIP unsupported recurrence | {event.calendar_key} | {event.summary}")
            continue

        google_events = google_events_by_calendar[event.calendar_key]
        if _google_has_equivalent_event(google_events, event):
            summary.skipped_existing += 1
            details.append(f"SKIP existing | {event.calendar_key} | {event.summary}")
            continue

        if dry_run:
            summary.inserted += 1
            details.append(_format_detail("DRY-RUN insert", event))
            continue

        command = _to_google_add_command(event)
        google_calendar_backend.add_event(google_service, command)
        google_events.append(_local_event_to_googleish_dict(event))
        summary.inserted += 1
        details.append(_format_detail("INSERTED", event))

    return summary, details


def _iter_local_events(service, start_date: date, end_date: date, selected: set[str]):
    seen: set[tuple] = set()
    for event in local_calendar_backend.list_events_range(service, start_date, end_date):
        calendar_key = _calendar_key_from_event(event)
        if calendar_key not in selected:
            continue
        key = (
            calendar_key,
            event.get("summary", ""),
            event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
            event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
            tuple(event.get("recurrence", []) or []),
        )
        if key in seen:
            continue
        seen.add(key)
        yield _normalize_local_event(calendar_key, event)


def _normalize_local_event(calendar_key: str, event: dict) -> LocalEventForSync:
    recurrence = list(event.get("recurrence") or [])
    start = event.get("start", {})
    end = event.get("end", {})

    if "dateTime" in start and "dateTime" in end:
        start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(utils.TZ)
        end_dt = datetime.fromisoformat(end["dateTime"]).astimezone(utils.TZ)
        return LocalEventForSync(
            calendar_key=calendar_key,
            summary=str(event.get("summary") or "(no title)"),
            start_date=start_dt.date(),
            end_date=end_dt.date(),
            start_time=start_dt.strftime("%H:%M"),
            end_time=end_dt.strftime("%H:%M"),
            all_day=False,
            recurrence=recurrence,
        )

    start_date_value = date.fromisoformat(start["date"])
    end_exclusive = date.fromisoformat(end["date"])
    return LocalEventForSync(
        calendar_key=calendar_key,
        summary=str(event.get("summary") or "(no title)"),
        start_date=start_date_value,
        end_date=end_exclusive - timedelta(days=1),
        start_time=None,
        end_time=None,
        all_day=True,
        recurrence=recurrence,
    )


def _calendar_key_from_event(event: dict) -> str:
    display = str(event.get("_calendar_name") or "").lower()
    if display in config.CALENDAR_DISPLAY_NAMES:
        return display
    for key, label in config.CALENDAR_DISPLAY_NAMES.items():
        if display == label.lower():
            return key
    return display


def _google_has_equivalent_event(events: list[dict], candidate: LocalEventForSync) -> bool:
    for event in events:
        if str(event.get("summary") or "") != candidate.summary:
            continue
        if list(event.get("recurrence") or []) != list(candidate.recurrence or []):
            continue

        start = event.get("start", {})
        end = event.get("end", {})
        if candidate.all_day:
            if start.get("date") != candidate.start_date.isoformat():
                continue
            expected_end = (candidate.end_date + timedelta(days=1)).isoformat()
            if end.get("date") != expected_end:
                continue
            return True

        if "dateTime" not in start or "dateTime" not in end:
            continue
        start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(utils.TZ)
        end_dt = datetime.fromisoformat(end["dateTime"]).astimezone(utils.TZ)
        if (
            start_dt.date() == candidate.start_date
            and end_dt.date() == candidate.end_date
            and start_dt.strftime("%H:%M") == candidate.start_time
            and end_dt.strftime("%H:%M") == candidate.end_time
        ):
            return True
    return False


def _to_google_add_command(event: LocalEventForSync) -> dict:
    command = {
        "calendar": event.calendar_key,
        "calendar_display": config.CALENDAR_DISPLAY_NAMES.get(event.calendar_key, event.calendar_key),
        "title": event.summary,
        "date": event.start_date,
        "all_day": event.all_day,
    }
    if event.recurrence:
        command["recurrence"] = list(event.recurrence)
    if event.end_date != event.start_date:
        command["end_date"] = event.end_date
    if not event.all_day:
        command["start"] = event.start_time
        command["end"] = event.end_time
    return command


def _local_event_to_googleish_dict(event: LocalEventForSync) -> dict:
    if event.all_day:
        return {
            "summary": event.summary,
            "start": {"date": event.start_date.isoformat()},
            "end": {"date": (event.end_date + timedelta(days=1)).isoformat()},
            "recurrence": list(event.recurrence),
        }
    start_dt = utils.make_datetime(event.start_date, event.start_time or "00:00")
    end_dt = utils.make_datetime(event.end_date, event.end_time or "00:00")
    return {
        "summary": event.summary,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": config.TIMEZONE},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": config.TIMEZONE},
        "recurrence": list(event.recurrence),
    }


def _is_supported_recurrence(recurrence: list[str]) -> bool:
    if not recurrence:
        return True
    if len(recurrence) != 1:
        return False
    rule = recurrence[0]
    return "FREQ=WEEKLY" in rule and "BYDAY=" in rule


def _format_detail(prefix: str, event: LocalEventForSync) -> str:
    if event.all_day:
        when = event.start_date.isoformat() if event.start_date == event.end_date else f"{event.start_date.isoformat()}..{event.end_date.isoformat()}"
    else:
        when = f"{event.start_date.isoformat()} {event.start_time}-{event.end_time}"
        if event.end_date != event.start_date:
            when = f"{event.start_date.isoformat()} {event.start_time}..{event.end_date.isoformat()} {event.end_time}"
    recurring = " recurring" if event.recurrence else ""
    return f"{prefix} | {event.calendar_key} | {event.summary} | {when}{recurring}"
