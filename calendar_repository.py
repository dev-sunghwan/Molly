"""
calendar_repository.py — Backend-agnostic calendar execution boundary.

This module selects the configured calendar backend once and exposes a stable,
deterministic repository interface to the rest of Molly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import config
import google_calendar_backend
import local_calendar_backend
import utils


@dataclass
class CalendarRepository:
    backend_name: str
    service: object
    backend_module: object

    @classmethod
    def from_config(cls) -> "CalendarRepository":
        backend_module = _select_backend_module(config.CALENDAR_BACKEND)
        service = backend_module.authenticate()
        return cls(
            backend_name=config.CALENDAR_BACKEND,
            service=service,
            backend_module=backend_module,
        )

    def list_events(self, target_date: date) -> list[dict]:
        return self.backend_module.list_events(self.service, target_date)

    def list_events_range(self, start_date: date, end_date: date) -> list[dict]:
        return self.backend_module.list_events_range(self.service, start_date, end_date)

    def add_event(self, command: dict) -> str:
        return self.backend_module.add_event(self.service, command)

    def find_and_edit_event(self, cal_key: str, target_date: date | None, title: str, changes: dict) -> str:
        return self.backend_module.find_and_edit_event(
            self.service,
            cal_key,
            target_date,
            title,
            changes,
        )

    def find_and_delete_event(self, cal_key: str, target_date: date | None, title: str) -> str:
        return self.backend_module.find_and_delete_event(
            self.service,
            cal_key,
            target_date,
            title,
        )

    def delete_recurring_series(self, cal_key: str, title: str) -> str:
        return self.backend_module.delete_recurring_series(self.service, cal_key, title)

    def search_events(self, keyword: str, days: int = 90) -> list[dict]:
        return self.backend_module.search_events(self.service, keyword, days=days)

    def get_next_events(self, cal_key: str | None, limit: int = 1) -> list[dict]:
        return self.backend_module.get_next_events(self.service, cal_key, limit=limit)

    def get_upcoming_events(self, cal_key: str | None, limit: int = 10) -> list[dict]:
        return self.backend_module.get_upcoming_events(self.service, cal_key, limit=limit)


def _select_backend_module(backend_name: str):
    normalized = backend_name.strip().lower()
    if normalized == "local":
        return local_calendar_backend
    if normalized == "google":
        return google_calendar_backend
    raise ValueError(f"Unsupported calendar backend: {backend_name}")


def format_search_results(events: list[dict], keyword: str) -> str:
    """Format search results — each event shows date + time + calendar."""
    if not events:
        return f"No upcoming events matching '{keyword}'."

    tz = utils.TZ
    lines = [f"<b>Search: '{keyword}'</b>"]
    for event in events:
        start = event.get("start", {})
        cal_label = event.get("_calendar_name", "")
        summary = event.get("summary", "(no title)")
        if "dateTime" in start:
            dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
            date_str = dt.strftime("%d-%m-%Y")
            time_str = dt.strftime("%H:%M")
            end = event.get("end", {})
            if "dateTime" in end:
                dt_end = datetime.fromisoformat(end["dateTime"]).astimezone(tz)
                time_str += f"–{dt_end.strftime('%H:%M')}"
        else:
            date_str = start.get("date", "?")
            time_str = "All day"
        lines.append(f"  • {date_str}  {time_str}  [{cal_label}] {summary}")

    return "\n".join(lines)


def format_upcoming_events(events: list[dict], cal_key: str | None, limit: int) -> str:
    """Format upcoming events — grouped by date, each line shows time + calendar + title."""
    if not events:
        label = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key) if cal_key else "any calendar"
        return f"No upcoming events in {label}."

    tz = utils.TZ
    label = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key) if cal_key else "All calendars"
    lines = [f"<b>Upcoming ({label}, next {limit}):</b>"]
    by_date: dict = {}

    for event in events:
        start = event.get("start", {})
        if "dateTime" in start:
            day = datetime.fromisoformat(start["dateTime"]).astimezone(tz).date()
        else:
            day = date.fromisoformat(start["date"])
        by_date.setdefault(day, []).append(event)

    for day, day_events in by_date.items():
        lines.append(f"\n<b>{day.strftime('%a %d-%m-%Y')}</b>")
        for event in day_events:
            start = event.get("start", {})
            cal_name = event.get("_calendar_name", "")
            summary = event.get("summary", "(no title)")
            if "dateTime" in start:
                dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
                time_str = dt.strftime("%H:%M")
                end = event.get("end", {})
                if "dateTime" in end:
                    dt_end = datetime.fromisoformat(end["dateTime"]).astimezone(tz)
                    time_str += f"–{dt_end.strftime('%H:%M')}"
            else:
                time_str = "All day"
            cal_part = f"[{cal_name}] " if not cal_key else ""
            lines.append(f"  • {time_str}  {cal_part}{summary}")

    return "\n".join(lines)


def format_next_events(events: list[dict], cal_key: str | None) -> str:
    """Format next event(s) — shows date + time + calendar."""
    if not events:
        label = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key) if cal_key else "any calendar"
        return f"No upcoming events in {label}."

    tz = utils.TZ
    label = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key) if cal_key else "all calendars"
    lines = [f"<b>Next event ({label}):</b>"]
    for event in events:
        start = event.get("start", {})
        cal_name = event.get("_calendar_name", "")
        summary = event.get("summary", "(no title)")
        if "dateTime" in start:
            dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
            date_str = dt.strftime("%d-%m-%Y")
            time_str = dt.strftime("%H:%M")
            end = event.get("end", {})
            if "dateTime" in end:
                dt_end = datetime.fromisoformat(end["dateTime"]).astimezone(tz)
                time_str += f"–{dt_end.strftime('%H:%M')}"
        else:
            date_str = start.get("date", "?")
            time_str = "All day"
        lines.append(f"  • {date_str}  {time_str}  [{cal_name}] {summary}")

    return "\n".join(lines)
