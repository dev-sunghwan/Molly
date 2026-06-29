#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
import google_calendar_backend


@dataclass
class CleanupCandidate:
    backend: str
    event_id: str
    calendar_key: str
    title: str
    start: str
    end: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Find or delete Molly test calendar events.")
    parser.add_argument(
        "--prefix",
        default="Molly ",
        help="Only match event titles starting with this exact prefix.",
    )
    parser.add_argument("--start-date", default="2026-04-01")
    parser.add_argument("--end-date", default="2026-12-31")
    parser.add_argument("--delete-local", action="store_true")
    parser.add_argument("--delete-google", action="store_true")
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)

    local_candidates = _local_candidates(args.prefix, start_date, end_date)
    google_candidates = _google_candidates(args.prefix, start_date, end_date)

    _print_candidates("local", local_candidates)
    _print_candidates("google", google_candidates)

    if args.delete_local:
        _delete_local(local_candidates)
    if args.delete_google:
        _delete_google(google_candidates)

    if not args.delete_local and not args.delete_google:
        print("Dry run only. Add --delete-local and/or --delete-google to delete matched events.")
    return 0


def _local_candidates(prefix: str, start_date: date, end_date: date) -> list[CleanupCandidate]:
    with sqlite3.connect(config.LOCAL_CALENDAR_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, calendar_key, summary, start_date, end_date, start_time, end_time
            FROM local_events
            WHERE summary LIKE ?
              AND start_date >= ?
              AND start_date <= ?
            ORDER BY start_date, start_time, summary
            """,
            (f"{prefix}%", start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
    return [
        CleanupCandidate(
            backend="local",
            event_id=str(row[0]),
            calendar_key=str(row[1]),
            title=str(row[2]),
            start=_format_local_when(row[3], row[5]),
            end=_format_local_when(row[4], row[6]),
        )
        for row in rows
    ]


def _google_candidates(prefix: str, start_date: date, end_date: date) -> list[CleanupCandidate]:
    service = google_calendar_backend.authenticate()
    events = google_calendar_backend.list_events_range(service, start_date, end_date)
    candidates: list[CleanupCandidate] = []
    for event in events:
        title = str(event.get("summary") or "")
        if not title.startswith(prefix):
            continue
        calendar_key = _calendar_key_from_event(event)
        candidates.append(
            CleanupCandidate(
                backend="google",
                event_id=str(event["id"]),
                calendar_key=calendar_key,
                title=title,
                start=_format_google_when(event.get("start", {})),
                end=_format_google_when(event.get("end", {})),
            )
        )
    return candidates


def _delete_local(candidates: list[CleanupCandidate]) -> None:
    if not candidates:
        print("No local events to delete.")
        return
    with sqlite3.connect(config.LOCAL_CALENDAR_DB_PATH) as conn:
        conn.executemany(
            "DELETE FROM local_events WHERE id = ?",
            [(candidate.event_id,) for candidate in candidates],
        )
    print(f"Deleted local events: {len(candidates)}")


def _delete_google(candidates: list[CleanupCandidate]) -> None:
    if not candidates:
        print("No Google events to delete.")
        return
    service = google_calendar_backend.authenticate()
    deleted = 0
    for candidate in candidates:
        cal_id = config.CALENDARS[candidate.calendar_key]
        service.events().delete(calendarId=cal_id, eventId=candidate.event_id).execute()
        deleted += 1
    print(f"Deleted Google events: {deleted}")


def _print_candidates(label: str, candidates: list[CleanupCandidate]) -> None:
    print(f"{label}: {len(candidates)}")
    for candidate in candidates:
        print(
            f"- {candidate.calendar_key} | {candidate.title} | "
            f"{candidate.start} -> {candidate.end} | id={candidate.event_id}"
        )


def _calendar_key_from_event(event: dict) -> str:
    display = str(event.get("_calendar_name") or "").lower()
    if display in config.CALENDAR_DISPLAY_NAMES:
        return display
    for key, label in config.CALENDAR_DISPLAY_NAMES.items():
        if display == label.lower():
            return key
    return display


def _format_local_when(date_value, time_value) -> str:
    if time_value:
        return f"{date_value} {time_value}"
    return str(date_value)


def _format_google_when(value: dict) -> str:
    if "date" in value:
        return str(value["date"])
    if "dateTime" not in value:
        return "?"
    dt = datetime.fromisoformat(value["dateTime"]).astimezone(google_calendar_backend.utils.TZ)
    return dt.strftime("%Y-%m-%d %H:%M")


if __name__ == "__main__":
    raise SystemExit(main())
