"""
local_calendar_backend.py — SQLite-backed local calendar execution backend.

This module provides a local replacement for the Google Calendar backend while
preserving the event dict shapes expected by Molly's existing formatters.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import config
import utils


@dataclass(frozen=True)
class LocalCalendarService:
    backend: str
    db_path: str


def authenticate() -> LocalCalendarService:
    _init_db()
    _seed_calendars()
    return LocalCalendarService(backend="local", db_path=str(config.LOCAL_CALENDAR_DB_PATH))


def list_events_range(service: LocalCalendarService, start_date: date, end_date: date) -> list[dict]:
    events = _expand_events(start_date, end_date)
    events.sort(key=_sort_key)
    return events


def list_events(service: LocalCalendarService, target_date: date) -> list[dict]:
    return list_events_range(service, target_date, target_date)


def add_event(service: LocalCalendarService, cmd: dict) -> str:
    event_id = str(uuid.uuid4())
    recurrence = json.dumps(cmd.get("recurrence", []))
    all_day = bool(cmd.get("all_day", False))
    end_date = cmd.get("end_date", cmd["date"])

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO local_events (
                id, calendar_key, summary, start_date, end_date,
                start_time, end_time, all_day, recurrence_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                cmd["calendar"],
                cmd["title"],
                cmd["date"].isoformat(),
                end_date.isoformat(),
                cmd.get("start"),
                cmd.get("end"),
                1 if all_day else 0,
                recurrence,
                datetime.now(utils.TZ).isoformat(),
            ),
        )

    cal_display = config.CALENDAR_DISPLAY_NAMES.get(cmd["calendar"], cmd["calendar"])
    if all_day:
        if "end_date" in cmd:
            reply_time_str = (
                f"All day  ({cmd['date'].strftime('%d-%m-%Y')} – {cmd['end_date'].strftime('%d-%m-%Y')})"
            )
        else:
            reply_time_str = "All day"
    else:
        reply_time_str = f"{cmd['start']}–{cmd['end']}"

    recurring_label = "  (weekly recurring)" if cmd.get("recurrence") else ""
    reply = (
        f"✅ Added to {cal_display}:\n"
        f"  {cmd['title']}\n"
        f"  {cmd['date'].strftime('%d-%m-%Y')}  {reply_time_str}{recurring_label}"
    )

    if not all_day:
        conflicts = _find_conflicts(
            cmd["calendar"],
            cmd["date"],
            cmd["start"],
            cmd["end"],
            cmd["title"],
            exclude_event_id=event_id,
        )
        if conflicts:
            lines = ["\n⚠️ Conflicts in same calendar:"]
            for ev in conflicts:
                start = ev["start"]
                end = ev["end"]
                dt = datetime.fromisoformat(start["dateTime"]).astimezone(utils.TZ)
                dt_end = datetime.fromisoformat(end["dateTime"]).astimezone(utils.TZ)
                lines.append(f"  • {dt.strftime('%H:%M')}–{dt_end.strftime('%H:%M')}  {ev.get('summary', '')}")
            reply += "\n".join(lines)
    return reply


def delete_recurring_series(service: LocalCalendarService, cal_key: str, title: str) -> str:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, recurrence_json FROM local_events
            WHERE calendar_key = ? AND lower(summary) = lower(?)
            """,
            (cal_key, title),
        ).fetchall()
        if not rows:
            return f"❌ No event '{title}' found in {config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key)} (next 90 days)"

        recurring = [row for row in rows if json.loads(row["recurrence_json"] or "[]")]
        if not recurring:
            if len(rows) > 1:
                return _multiple_matches_message(cal_key, title, _expanded_matches(cal_key, title, None))
            conn.execute("DELETE FROM local_events WHERE id = ?", (rows[0]["id"],))
            return (
                f"Deleted from {config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key)}:\n"
                f"  {title}\n  (not a recurring event — single occurrence deleted)"
            )

        if len(recurring) > 1:
            return _multiple_matches_message(cal_key, title, _expanded_matches(cal_key, title, None))

        conn.execute("DELETE FROM local_events WHERE id = ?", (recurring[0]["id"],))
        return f"Deleted entire series from {config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key)}:\n  {title}"


def find_and_edit_event(
    service: LocalCalendarService,
    cal_key: str,
    target_date: date | None,
    title: str,
    changes: dict,
) -> str:
    matches = _expanded_matches(cal_key, title, target_date)
    cal_display = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key)
    search_desc = f"on {target_date.strftime('%d-%m-%Y')}" if target_date else "in the next 90 days"

    if not matches:
        return f"❌ No event '{title}' found in {cal_display} {search_desc}"
    if len(matches) > 1:
        return _multiple_matches_message(cal_key, title, matches, action="changed")

    match = matches[0]
    if match.get("recurringEventId"):
        return f"❌ Recurring event edits are not supported yet in the local backend. Use delete all and recreate the series."

    row = match["_source_row"]
    new_title = changes.get("title", row["summary"])
    new_date = changes.get("date", date.fromisoformat(row["start_date"]))
    start_time = row["start_time"]
    end_time = row["end_time"]
    all_day = bool(row["all_day"])
    end_date_value = date.fromisoformat(row["end_date"])

    if "start" in changes and "end" in changes:
        start_time = changes["start"]
        end_time = changes["end"]
        all_day = False
        end_date_value = new_date
    elif "date" in changes and not all_day:
        end_date_value = new_date
    elif "date" in changes and all_day:
        duration_days = (date.fromisoformat(row["end_date"]) - date.fromisoformat(row["start_date"])).days
        end_date_value = new_date + timedelta(days=duration_days)

    with _connect() as conn:
        conn.execute(
            """
            UPDATE local_events
            SET summary = ?, start_date = ?, end_date = ?, start_time = ?, end_time = ?, all_day = ?
            WHERE id = ?
            """,
            (
                new_title,
                new_date.isoformat(),
                end_date_value.isoformat(),
                start_time,
                end_time,
                1 if all_day else 0,
                row["id"],
            ),
        )

    if all_day:
        time_disp = "All day"
    else:
        time_disp = f"{start_time}–{end_time}"
    return (
        f"✅ Updated in {cal_display}:\n"
        f"  {new_title}\n"
        f"  {new_date.strftime('%d-%m-%Y')}  {time_disp}"
    )


def find_and_delete_event(
    service: LocalCalendarService,
    cal_key: str,
    target_date: date | None,
    title: str,
) -> str:
    matches = _expanded_matches(cal_key, title, target_date)
    cal_display = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key)
    search_desc = f"on {target_date.strftime('%d-%m-%Y')}" if target_date else "in the next 90 days"

    if not matches:
        return f"❌ No event '{title}' found in {cal_display} {search_desc}"
    if len(matches) > 1:
        return _multiple_matches_message(cal_key, title, matches, action="deleted")

    match = matches[0]
    if match.get("recurringEventId"):
        return f"❌ Recurring event deletion by single occurrence is not supported yet in the local backend. Use delete all."

    row = match["_source_row"]
    with _connect() as conn:
        conn.execute("DELETE FROM local_events WHERE id = ?", (row["id"],))
    return f"Deleted from {cal_display}:\n  {title}\n  {match['_display_date']}"


def search_events(service: LocalCalendarService, keyword: str, days: int = 90) -> list[dict]:
    kw = keyword.lower()
    events = _expand_events(utils._today_local(), utils._today_local() + timedelta(days=days))
    return [ev for ev in events if kw in ev.get("summary", "").lower()]


def get_next_events(service: LocalCalendarService, cal_key: str | None, limit: int = 1) -> list[dict]:
    events = get_upcoming_events(service, cal_key, limit)
    return events[:limit]


def get_upcoming_events(service: LocalCalendarService, cal_key: str | None, limit: int = 10) -> list[dict]:
    events = _expand_events(utils._today_local(), utils._today_local() + timedelta(days=365), calendar_key=cal_key)
    events.sort(key=_sort_key)
    return events[:limit]


def _connect() -> sqlite3.Connection:
    config.LOCAL_CALENDAR_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.LOCAL_CALENDAR_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS local_calendars (
                key TEXT PRIMARY KEY,
                display_name TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS local_events (
                id TEXT PRIMARY KEY,
                calendar_key TEXT NOT NULL,
                summary TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                all_day INTEGER NOT NULL DEFAULT 0,
                recurrence_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                source_backend TEXT,
                source_event_id TEXT
            )
            """
        )
        _ensure_column(conn, "local_events", "source_backend", "TEXT")
        _ensure_column(conn, "local_events", "source_event_id", "TEXT")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_local_events_source_unique
            ON local_events (source_backend, source_event_id)
            WHERE source_backend IS NOT NULL AND source_event_id IS NOT NULL
            """
        )


def _seed_calendars() -> None:
    with _connect() as conn:
        for key, display_name in config.CALENDAR_DISPLAY_NAMES.items():
            conn.execute(
                """
                INSERT INTO local_calendars (key, display_name)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET display_name = excluded.display_name
                """,
                (key, display_name),
            )


def import_event(
    service: LocalCalendarService,
    *,
    calendar_key: str,
    summary: str,
    start_date_value: date,
    end_date_value: date,
    start_time: str | None,
    end_time: str | None,
    all_day: bool,
    recurrence: list[str] | None = None,
    source_backend: str | None = None,
    source_event_id: str | None = None,
) -> str:
    _ = service
    event_id = str(uuid.uuid4())
    recurrence_json = json.dumps(recurrence or [])

    with _connect() as conn:
        if source_backend and source_event_id:
            existing = conn.execute(
                """
                SELECT id FROM local_events
                WHERE source_backend = ? AND source_event_id = ?
                """,
                (source_backend, source_event_id),
            ).fetchone()
            if existing is not None:
                return "duplicate"

        conn.execute(
            """
            INSERT INTO local_events (
                id, calendar_key, summary, start_date, end_date,
                start_time, end_time, all_day, recurrence_json, created_at,
                source_backend, source_event_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                calendar_key,
                summary,
                start_date_value.isoformat(),
                end_date_value.isoformat(),
                start_time,
                end_time,
                1 if all_day else 0,
                recurrence_json,
                datetime.now(utils.TZ).isoformat(),
                source_backend,
                source_event_id,
            ),
        )
    return "imported"


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
    existing_columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name in existing_columns:
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _expand_events(start_date: date, end_date: date, calendar_key: str | None = None) -> list[dict]:
    query = "SELECT * FROM local_events"
    params: tuple = ()
    if calendar_key is not None:
        query += " WHERE calendar_key = ?"
        params = (calendar_key,)

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()

    all_events: list[dict] = []
    for row in rows:
        all_events.extend(_expand_row(row, start_date, end_date))
    return all_events


def _expand_row(row: sqlite3.Row, start_date: date, end_date: date) -> list[dict]:
    recurrence = json.loads(row["recurrence_json"] or "[]")
    if recurrence:
        return _expand_recurring_row(row, start_date, end_date, recurrence)

    event_start = date.fromisoformat(row["start_date"])
    event_end = date.fromisoformat(row["end_date"])
    if event_end < start_date or event_start > end_date:
        return []
    return [_row_to_event(row, event_start)]


def _expand_recurring_row(row: sqlite3.Row, start_date: date, end_date: date, recurrence: list[str]) -> list[dict]:
    byday = _extract_byday(recurrence)
    if byday is None:
        return []

    first_date = date.fromisoformat(row["start_date"])
    target_weekday = _rrule_to_weekday(byday)
    if target_weekday is None:
        return []

    cursor = max(start_date, first_date)
    while cursor.weekday() != target_weekday:
        cursor += timedelta(days=1)

    occurrences: list[dict] = []
    while cursor <= end_date:
        if cursor >= first_date:
            occurrences.append(_row_to_event(row, cursor, recurring=True))
        cursor += timedelta(days=7)
    return occurrences


def _row_to_event(row: sqlite3.Row, occurrence_date: date, recurring: bool = False) -> dict:
    event: dict = {
        "id": row["id"] if not recurring else f"{row['id']}:{occurrence_date.isoformat()}",
        "summary": row["summary"],
        "_calendar_name": config.CALENDAR_DISPLAY_NAMES.get(row["calendar_key"], row["calendar_key"]),
        "_source_row": row,
        "_display_date": occurrence_date.strftime("%d-%m-%Y"),
    }

    if recurring:
        event["recurringEventId"] = row["id"]

    if row["all_day"]:
        end_date_value = occurrence_date + (date.fromisoformat(row["end_date"]) - date.fromisoformat(row["start_date"]))
        event["start"] = {"date": occurrence_date.isoformat()}
        event["end"] = {"date": (end_date_value + timedelta(days=1)).isoformat()}
        return event

    start_dt = utils.make_datetime(occurrence_date, row["start_time"])
    end_dt = utils.make_datetime(occurrence_date, row["end_time"])
    event["start"] = {"dateTime": start_dt.isoformat(), "timeZone": config.TIMEZONE}
    event["end"] = {"dateTime": end_dt.isoformat(), "timeZone": config.TIMEZONE}
    return event


def _find_conflicts(
    calendar_key: str,
    event_date: date,
    start_str: str,
    end_str: str,
    new_title: str,
    exclude_event_id: str | None = None,
) -> list[dict]:
    new_start = utils.make_datetime(event_date, start_str)
    new_end = utils.make_datetime(event_date, end_str)
    candidates = _expand_events(event_date, event_date, calendar_key=calendar_key)
    conflicts: list[dict] = []
    for ev in candidates:
        if ev.get("summary", "") == new_title:
            continue
        if exclude_event_id and ev.get("id", "").split(":")[0] == exclude_event_id:
            continue
        start = ev.get("start", {})
        if "dateTime" not in start:
            continue
        ev_start = datetime.fromisoformat(start["dateTime"]).astimezone(utils.TZ)
        ev_end = datetime.fromisoformat(ev.get("end", {})["dateTime"]).astimezone(utils.TZ)
        if new_start < ev_end and new_end > ev_start:
            conflicts.append(ev)
    return conflicts


def _expanded_matches(cal_key: str, title: str, target_date: date | None) -> list[dict]:
    start_date = target_date or utils._today_local()
    end_date = target_date or (utils._today_local() + timedelta(days=90))
    candidates = _expand_events(start_date, end_date, calendar_key=cal_key)
    return [ev for ev in candidates if ev.get("summary", "").lower() == title.lower()]


def _multiple_matches_message(cal_key: str, title: str, matches: list[dict], action: str = "changed") -> str:
    cal_display = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key)
    lines = [f"❌ Multiple events named '{title}' in {cal_display}. Nothing {action}. Specify a date:\n"]
    for event in matches:
        start = event.get("start", {})
        if "dateTime" in start:
            dt = datetime.fromisoformat(start["dateTime"]).astimezone(utils.TZ)
            lines.append(f"  • {dt.strftime('%d-%m-%Y')}  {dt.strftime('%H:%M')}  {event.get('summary')}")
        else:
            lines.append(f"  • {start.get('date', '?')}  All day  {event.get('summary')}")
    return "\n".join(lines)


def _extract_byday(recurrence: list[str]) -> str | None:
    for item in recurrence:
        if "BYDAY=" in item:
            return item.split("BYDAY=", 1)[1].split(";", 1)[0]
    return None


def _rrule_to_weekday(byday: str) -> int | None:
    mapping = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
    return mapping.get(byday)


def _sort_key(ev: dict) -> str:
    start = ev.get("start", {})
    return start.get("dateTime", start.get("date", ""))
