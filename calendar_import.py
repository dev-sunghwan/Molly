"""
Helpers for importing Google Calendar data into Molly's local calendar backend.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import config
import google_calendar_backend
import local_calendar_backend
import utils


@dataclass
class ImportSummary:
    imported: int = 0
    skipped_duplicates: int = 0
    skipped_unsupported: int = 0
    skipped_cancelled: int = 0


def import_google_to_local(
    start_date: date,
    end_date: date,
    *,
    dry_run: bool = False,
) -> tuple[ImportSummary, list[str]]:
    google_service = google_calendar_backend.authenticate()
    local_service = local_calendar_backend.authenticate()
    summary = ImportSummary()
    details: list[str] = []

    for calendar_key, calendar_id in config.CALENDARS.items():
        events = _fetch_google_events(google_service, calendar_id, start_date, end_date)
        for event in events:
            status, detail = _import_one_event(
                local_service,
                calendar_key=calendar_key,
                event=event,
                dry_run=dry_run,
            )
            details.append(detail)
            if status == "imported":
                summary.imported += 1
            elif status == "duplicate":
                summary.skipped_duplicates += 1
            elif status == "cancelled":
                summary.skipped_cancelled += 1
            else:
                summary.skipped_unsupported += 1

    return summary, details


def _fetch_google_events(service, calendar_id: str, start_date: date, end_date: date) -> list[dict]:
    tz = utils.TZ
    time_min = tz.localize(datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)).isoformat()
    time_max = tz.localize(datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)).isoformat()

    result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=False,
            showDeleted=False,
        )
        .execute()
    )
    return result.get("items", [])


def _import_one_event(
    local_service: local_calendar_backend.LocalCalendarService,
    *,
    calendar_key: str,
    event: dict,
    dry_run: bool,
) -> tuple[str, str]:
    source_event_id = str(event.get("id", ""))
    summary = str(event.get("summary") or "(no title)")

    if event.get("status") == "cancelled":
        return "cancelled", f"SKIP cancelled | {calendar_key} | {summary}"

    recurrence = event.get("recurrence", [])
    if recurrence and not _is_supported_recurrence(recurrence):
        return "unsupported", f"SKIP unsupported recurrence | {calendar_key} | {summary}"

    normalized = _normalize_google_event(event)
    if normalized is None:
        return "unsupported", f"SKIP unsupported event shape | {calendar_key} | {summary}"

    if dry_run:
        return "imported", (
            f"DRY-RUN import | {calendar_key} | {summary} | "
            f"{normalized['start_date']} {normalized.get('start_time') or 'all-day'}"
        )

    status = local_calendar_backend.import_event(
        local_service,
        calendar_key=calendar_key,
        summary=summary,
        start_date_value=normalized["start_date"],
        end_date_value=normalized["end_date"],
        start_time=normalized.get("start_time"),
        end_time=normalized.get("end_time"),
        all_day=normalized["all_day"],
        recurrence=recurrence,
        source_backend="google_calendar",
        source_event_id=source_event_id,
    )
    return status, f"{status.upper()} | {calendar_key} | {summary}"


def _normalize_google_event(event: dict) -> dict | None:
    start = event.get("start", {})
    end = event.get("end", {})

    if "dateTime" in start and "dateTime" in end:
        start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(utils.TZ)
        end_dt = datetime.fromisoformat(end["dateTime"]).astimezone(utils.TZ)
        return {
            "all_day": False,
            "start_date": start_dt.date(),
            "end_date": end_dt.date(),
            "start_time": start_dt.strftime("%H:%M"),
            "end_time": end_dt.strftime("%H:%M"),
        }

    if "date" in start and "date" in end:
        start_date_value = date.fromisoformat(start["date"])
        end_exclusive = date.fromisoformat(end["date"])
        end_date_value = end_exclusive - timedelta(days=1)
        return {
            "all_day": True,
            "start_date": start_date_value,
            "end_date": end_date_value,
            "start_time": None,
            "end_time": None,
        }

    return None


def _is_supported_recurrence(recurrence: list[str]) -> bool:
    if len(recurrence) != 1:
        return False
    rule = recurrence[0]
    return "FREQ=WEEKLY" in rule and "BYDAY=" in rule
