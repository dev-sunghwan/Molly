"""
calendar_client.py — All Google Calendar API interactions.

Public API:
  authenticate()          → builds and returns a GCal service object
  list_events(service, date)      → list[dict]  (events on that date, all calendars)
  add_event(service, cmd)         → str          (confirmation message)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytz
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config
import local_calendar_backend
import utils

SCOPES = ["https://www.googleapis.com/auth/calendar"]


# ── Authentication ────────────────────────────────────────────────────────────

def authenticate():
    """
    Authenticate with Google Calendar using OAuth 2.0.
    - Loads token.json if it exists and is valid (or refreshes it).
    - Opens a browser for the consent flow on first run.
    Returns a Google API service object.
    """
    if config.CALENDAR_BACKEND == "local":
        return local_calendar_backend.authenticate()

    creds = None

    if config.TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(config.TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(config.CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save token for next run
        config.TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=creds)


# ── Read events (range) ───────────────────────────────────────────────────────

def list_events_range(service, start_date: date, end_date: date) -> list[dict]:
    """
    Return all events from start_date to end_date (inclusive) across all calendars,
    sorted by start time.
    """
    if getattr(service, "backend", None) == "local":
        return local_calendar_backend.list_events_range(service, start_date, end_date)

    tz = utils.TZ
    time_min = tz.localize(datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)).isoformat()
    time_max = tz.localize(datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)).isoformat()

    all_events: list[dict] = []

    for name, cal_id in config.CALENDARS.items():
        try:
            result = (
                service.events()
                .list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            for event in result.get("items", []):
                event["_calendar_name"] = config.CALENDAR_DISPLAY_NAMES.get(name, name)
                all_events.append(event)
        except HttpError as e:
            print(f"[GCal] Error reading calendar '{name}': {e}")

    def sort_key(ev):
        start = ev.get("start", {})
        return start.get("dateTime", start.get("date", ""))

    all_events.sort(key=sort_key)
    return all_events


# ── Read events ───────────────────────────────────────────────────────────────

def list_events(service, target_date: date) -> list[dict]:
    """
    Return all events on target_date across all 6 calendars,
    sorted by start time. Each event dict has an extra '_calendar_name' key.
    """
    tz = utils.TZ
    start_of_day = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0))
    end_of_day   = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59))

    time_min = start_of_day.isoformat()
    time_max = end_of_day.isoformat()

    all_events: list[dict] = []

    for name, cal_id in config.CALENDARS.items():
        try:
            result = (
                service.events()
                .list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            for event in result.get("items", []):
                event["_calendar_name"] = config.CALENDAR_DISPLAY_NAMES.get(name, name)
                all_events.append(event)
        except HttpError as e:
            # Log and continue — don't fail the whole request over one calendar
            print(f"[GCal] Error reading calendar '{name}': {e}")

    # Sort all events by start time across all calendars
    def sort_key(ev):
        start = ev.get("start", {})
        return start.get("dateTime", start.get("date", ""))

    all_events.sort(key=sort_key)
    return all_events


# ── Write events ──────────────────────────────────────────────────────────────

def add_event(service, cmd: dict) -> str:
    """
    Insert an event into the specified calendar.
    cmd comes from commands.parse() with cmd["cmd"] == "add".
    Supports timed events, all-day events, and weekly recurring events.
    Returns a confirmation string to send back via Telegram.
    """
    cal_id = config.CALENDARS[cmd["calendar"]]
    cal_display = config.CALENDAR_DISPLAY_NAMES.get(cmd["calendar"], cmd["calendar"])
    all_day = cmd.get("all_day", False)

    if all_day:
        start_date_str = cmd["date"].strftime("%Y-%m-%d")
        # Multi-day: end date in Google Calendar API is exclusive, so add 1 day
        if "end_date" in cmd:
            end_date_exclusive = cmd["end_date"] + timedelta(days=1)
            end_date_str = end_date_exclusive.strftime("%Y-%m-%d")
            reply_time_str = f"All day  ({cmd['date'].strftime('%d-%m-%Y')} – {cmd['end_date'].strftime('%d-%m-%Y')})"
        else:
            end_date_str = start_date_str
            reply_time_str = "All day"
        event_body = {
            "summary": cmd["title"],
            "start": {"date": start_date_str},
            "end":   {"date": end_date_str},
        }
    else:
        start_dt = utils.make_datetime(cmd["date"], cmd["start"])
        end_dt   = utils.make_datetime(cmd["date"], cmd["end"])
        event_body = {
            "summary": cmd["title"],
            "start": {"dateTime": start_dt.isoformat(), "timeZone": config.TIMEZONE},
            "end":   {"dateTime": end_dt.isoformat(),   "timeZone": config.TIMEZONE},
        }
        reply_time_str = f"{cmd['start']}–{cmd['end']}"

    if "recurrence" in cmd:
        event_body["recurrence"] = cmd["recurrence"]

    try:
        service.events().insert(calendarId=cal_id, body=event_body).execute()
        date_str_display = cmd["date"].strftime("%d-%m-%Y")
        recurring_label = "  (weekly recurring)" if "recurrence" in cmd else ""
        reply = (
            f"✅ Added to {cal_display}:\n"
            f"  {cmd['title']}\n"
            f"  {date_str_display}  {reply_time_str}{recurring_label}"
        )
        # Conflict check — only for timed events (all-day events can't conflict on time)
        if not all_day:
            conflicts = _find_conflicts(service, cal_id, cmd["date"],
                                        cmd["start"], cmd["end"], cmd["title"])
            if conflicts:
                tz = utils.TZ
                lines = ["\n⚠️ Conflicts in same calendar:"]
                for ev in conflicts:
                    s = ev.get("start", {})
                    dt = datetime.fromisoformat(s["dateTime"]).astimezone(tz)
                    e_end = ev.get("end", {})
                    dt_end = datetime.fromisoformat(e_end["dateTime"]).astimezone(tz)
                    lines.append(f"  • {dt.strftime('%H:%M')}–{dt_end.strftime('%H:%M')}  {ev.get('summary', '')}")
                reply += "\n".join(lines)
        return reply
    except HttpError as e:
        return f"❌ Failed to add event: {e}"


def _find_conflicts(service, cal_id: str, event_date, start_str: str, end_str: str, new_title: str) -> list[dict]:
    """Return existing timed events in cal_id that overlap with start_str–end_str on event_date."""
    tz = utils.TZ
    new_start = utils.make_datetime(event_date, start_str)
    new_end   = utils.make_datetime(event_date, end_str)
    time_min  = tz.localize(datetime(event_date.year, event_date.month, event_date.day, 0, 0, 0)).isoformat()
    time_max  = tz.localize(datetime(event_date.year, event_date.month, event_date.day, 23, 59, 59)).isoformat()
    try:
        result = (
            service.events()
            .list(calendarId=cal_id, timeMin=time_min, timeMax=time_max,
                  singleEvents=True, orderBy="startTime")
            .execute()
        )
    except HttpError:
        return []
    conflicts = []
    for ev in result.get("items", []):
        s = ev.get("start", {})
        if "dateTime" not in s:
            continue  # skip all-day
        if ev.get("summary", "") == new_title:
            continue  # the event we just added
        ev_start = datetime.fromisoformat(s["dateTime"]).astimezone(tz)
        ev_end   = datetime.fromisoformat(ev.get("end", {})["dateTime"]).astimezone(tz)
        # Overlap: new_start < ev_end  AND  new_end > ev_start
        if new_start < ev_end and new_end > ev_start:
            conflicts.append(ev)
    return conflicts


# ── Delete recurring series ───────────────────────────────────────────────────

def delete_recurring_series(service, cal_key: str, title: str) -> str:
    """
    Find a recurring event by title and delete the entire series (master event).
    Searches the next 90 days for an instance, then deletes the master.
    - 0 matches → not found
    - 1 recurring match → master deleted
    - 1 non-recurring match → single event deleted (with note)
    - 2+ matches → list them, nothing deleted
    """
    cal_id = config.CALENDARS[cal_key]
    cal_display = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key)
    tz = utils.TZ
    today = utils._today_local()
    end = today + timedelta(days=90)
    time_min = tz.localize(datetime(today.year, today.month, today.day, 0, 0, 0)).isoformat()
    time_max = tz.localize(datetime(end.year, end.month, end.day, 23, 59, 59)).isoformat()

    try:
        result = (
            service.events()
            .list(calendarId=cal_id, timeMin=time_min, timeMax=time_max,
                  singleEvents=True, orderBy="startTime")
            .execute()
        )
        events = result.get("items", [])
        matches = [e for e in events if e.get("summary", "").lower() == title.lower()]

        if not matches:
            return f"❌ No event '{title}' found in {cal_display} (next 90 days)"

        if len(matches) > 1:
            lines = [f"❌ Multiple events named '{title}' in {cal_display}. Nothing deleted. Specify with 'delete':\n"]
            seen = set()
            for e in matches:
                master_id = e.get("recurringEventId", e.get("id", ""))
                if master_id in seen:
                    continue
                seen.add(master_id)
                start = e.get("start", {})
                if "dateTime" in start:
                    dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
                    lines.append(f"  • {dt.strftime('%d-%m-%Y')}  {dt.strftime('%H:%M')}  {e.get('summary')}")
                else:
                    lines.append(f"  • {start.get('date', '?')}  All day  {e.get('summary')}")
            return "\n".join(lines)

        event = matches[0]
        recurring_event_id = event.get("recurringEventId")

        if recurring_event_id:
            # Delete the master event — removes the entire series
            service.events().delete(calendarId=cal_id, eventId=recurring_event_id).execute()
            return f"Deleted entire series from {cal_display}:\n  {title}"
        else:
            # Not a recurring event — delete the single instance
            service.events().delete(calendarId=cal_id, eventId=event["id"]).execute()
            return f"Deleted from {cal_display}:\n  {title}\n  (not a recurring event — single occurrence deleted)"

    except HttpError as e:
        return f"❌ Failed to delete series: {e}"


# ── Edit event ───────────────────────────────────────────────────────────────

def find_and_edit_event(service, cal_key: str, target_date: date | None, title: str, changes: dict) -> str:
    """
    Find an event by calendar and title, then apply changes.

    target_date: if provided, search only that day.
                 if None, search the next 90 days (upcoming events).

    changes keys (all optional):
      "start", "end"  — new time strings "HH:MM"
      "date"          — new date object (reschedule)
      "title"         — new title string

    - 0 matches → not found message
    - 1 match   → patched, confirmation
    - 2+ matches → list them with dates, nothing changed
    """
    cal_id = config.CALENDARS[cal_key]
    cal_display = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key)
    tz = utils.TZ

    if target_date is not None:
        date_str = target_date.strftime("%d-%m-%Y")
        time_min = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)).isoformat()
        time_max = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)).isoformat()
        search_desc = f"on {date_str}"
    else:
        today = utils._today_local()
        end = today + timedelta(days=90)
        time_min = tz.localize(datetime(today.year, today.month, today.day, 0, 0, 0)).isoformat()
        time_max = tz.localize(datetime(end.year, end.month, end.day, 23, 59, 59)).isoformat()
        date_str = None
        search_desc = "in the next 90 days"

    try:
        result = (
            service.events()
            .list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = result.get("items", [])
        matches = [e for e in events if e.get("summary", "").lower() == title.lower()]

        if not matches:
            return f"❌ No event '{title}' found in {cal_display} {search_desc}"

        if len(matches) > 1:
            lines = [f"❌ Multiple events named '{title}' in {cal_display}. Nothing changed. Specify a date:\n"]
            for e in matches:
                start = e.get("start", {})
                if "dateTime" in start:
                    dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
                    lines.append(f"  • {dt.strftime('%d-%m-%Y')}  {dt.strftime('%H:%M')}  {e.get('summary')}")
                else:
                    lines.append(f"  • {start.get('date', '?')}  All day  {e.get('summary')}")
            return "\n".join(lines)

        event = matches[0]
        existing_start = event.get("start", {})
        existing_end   = event.get("end", {})
        is_all_day = "date" in existing_start

        # Build update body starting from the full existing event.
        # Using update() (not patch()) ensures conflicting fields (e.g. date vs
        # dateTime) are fully replaced rather than merged, which is required
        # when converting an all-day event to a timed event.
        update_body = dict(event)

        if "title" in changes:
            update_body["summary"] = changes["title"]

        if "date" in changes:
            new_date = changes["date"]
            if not is_all_day:
                # Timed event — preserve the time, move to new date
                old_start_dt = datetime.fromisoformat(existing_start["dateTime"]).astimezone(tz)
                old_end_dt   = datetime.fromisoformat(existing_end["dateTime"]).astimezone(tz)
                new_start_dt = tz.localize(datetime(new_date.year, new_date.month, new_date.day,
                                                     old_start_dt.hour, old_start_dt.minute))
                new_end_dt   = tz.localize(datetime(new_date.year, new_date.month, new_date.day,
                                                     old_end_dt.hour, old_end_dt.minute))
                update_body["start"] = {"dateTime": new_start_dt.isoformat(), "timeZone": config.TIMEZONE}
                update_body["end"]   = {"dateTime": new_end_dt.isoformat(),   "timeZone": config.TIMEZONE}
            else:
                # All-day event — change the date, stay all-day
                update_body["start"] = {"date": new_date.strftime("%Y-%m-%d")}
                update_body["end"]   = {"date": new_date.strftime("%Y-%m-%d")}

        if "start" in changes and "end" in changes:
            # Change time (possibly converting all-day → timed)
            if is_all_day:
                event_date_obj = date.fromisoformat(existing_start["date"])
            else:
                event_date_obj = datetime.fromisoformat(existing_start["dateTime"]).astimezone(tz).date()

            new_start_dt = utils.make_datetime(event_date_obj, changes["start"])
            new_end_dt   = utils.make_datetime(event_date_obj, changes["end"])
            # Replace start/end entirely — clears the old 'date' key for all-day events
            update_body["start"] = {"dateTime": new_start_dt.isoformat(), "timeZone": config.TIMEZONE}
            update_body["end"]   = {"dateTime": new_end_dt.isoformat(),   "timeZone": config.TIMEZONE}

        if update_body == dict(event) and "title" not in changes:
            return "❌ No changes specified."

        service.events().update(calendarId=cal_id, eventId=event["id"], body=update_body).execute()

        # Build confirmation message
        new_title  = changes.get("title", event.get("summary", title))
        new_date_d = changes.get("date", target_date)
        date_disp  = new_date_d.strftime("%d-%m-%Y") if new_date_d else "?"

        if "start" in changes:
            time_disp = f"{changes['start']}–{changes['end']}"
        elif not is_all_day:
            old_dt     = datetime.fromisoformat(existing_start["dateTime"]).astimezone(tz)
            old_end_dt = datetime.fromisoformat(existing_end["dateTime"]).astimezone(tz)
            time_disp  = f"{old_dt.strftime('%H:%M')}–{old_end_dt.strftime('%H:%M')}"
        else:
            time_disp = "All day"

        return (
            f"✅ Updated in {cal_display}:\n"
            f"  {new_title}\n"
            f"  {date_disp}  {time_disp}"
        )

    except HttpError as e:
        return f"❌ Failed to edit event: {e}"


# ── Delete event ──────────────────────────────────────────────────────────────

def find_and_delete_event(service, cal_key: str, target_date: date | None, title: str) -> str:
    """
    Find an event by title in a specific calendar and delete it.

    target_date: if provided, search only that day.
                 if None, search the next 90 days.

    - 0 matches → not found message
    - 1 match   → deleted, confirmation
    - 2+ matches → list them with dates, nothing deleted
    """
    cal_id = config.CALENDARS[cal_key]
    cal_display = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key)
    tz = utils.TZ

    if target_date is not None:
        date_str = target_date.strftime("%d-%m-%Y")
        time_min = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)).isoformat()
        time_max = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)).isoformat()
        search_desc = f"on {date_str}"
    else:
        today = utils._today_local()
        end = today + timedelta(days=90)
        time_min = tz.localize(datetime(today.year, today.month, today.day, 0, 0, 0)).isoformat()
        time_max = tz.localize(datetime(end.year, end.month, end.day, 23, 59, 59)).isoformat()
        date_str = None
        search_desc = "in the next 90 days"

    try:
        result = (
            service.events()
            .list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = result.get("items", [])
        matches = [e for e in events if e.get("summary", "").lower() == title.lower()]

        if not matches:
            return f"❌ No event '{title}' found in {cal_display} {search_desc}"

        if len(matches) > 1:
            lines = [f"❌ Multiple events named '{title}' in {cal_display}. Nothing deleted. Specify a date:\n"]
            for e in matches:
                start = e.get("start", {})
                if "dateTime" in start:
                    dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
                    lines.append(f"  • {dt.strftime('%d-%m-%Y')}  {dt.strftime('%H:%M')}  {e.get('summary')}")
                else:
                    lines.append(f"  • {start.get('date', '?')}  All day  {e.get('summary')}")
            return "\n".join(lines)

        event = matches[0]
        ev_start = event.get("start", {})
        if "dateTime" in ev_start:
            ev_date_str = datetime.fromisoformat(ev_start["dateTime"]).astimezone(tz).strftime("%d-%m-%Y")
        else:
            ev_date_str = ev_start.get("date", "?")
        service.events().delete(calendarId=cal_id, eventId=event["id"]).execute()
        return f"Deleted from {cal_display}:\n  {title}\n  {ev_date_str}"

    except HttpError as e:
        return f"❌ Failed to delete event: {e}"


# ── Search events ─────────────────────────────────────────────────────────────

def search_events(service, keyword: str, days: int = 90) -> list[dict]:
    """
    Search for events containing keyword (case-insensitive) across all calendars
    in the next `days` days. Returns events sorted by start time.
    """
    tz = utils.TZ
    today = utils._today_local()
    end = today + timedelta(days=days)
    time_min = tz.localize(datetime(today.year, today.month, today.day, 0, 0, 0)).isoformat()
    time_max = tz.localize(datetime(end.year, end.month, end.day, 23, 59, 59)).isoformat()
    kw = keyword.lower()

    all_events: list[dict] = []
    for name, cal_id in config.CALENDARS.items():
        try:
            result = (
                service.events()
                .list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    q=keyword,  # server-side keyword filter
                )
                .execute()
            )
            for event in result.get("items", []):
                # Also filter client-side so partial matches are consistent
                if kw in event.get("summary", "").lower():
                    event["_calendar_name"] = config.CALENDAR_DISPLAY_NAMES.get(name, name)
                    all_events.append(event)
        except HttpError as e:
            print(f"[GCal] Error searching calendar '{name}': {e}")

    def sort_key(ev):
        start = ev.get("start", {})
        return start.get("dateTime", start.get("date", ""))

    all_events.sort(key=sort_key)
    return all_events


def format_search_results(events: list[dict], keyword: str) -> str:
    """Format search results — each event shows date + time + calendar."""
    if not events:
        return f"No upcoming events matching '{keyword}'."

    tz = utils.TZ
    lines = [f"<b>Search: '{keyword}'</b>"]
    for ev in events:
        start = ev.get("start", {})
        cal_label = ev.get("_calendar_name", "")
        summary = ev.get("summary", "(no title)")
        if "dateTime" in start:
            dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
            date_str = dt.strftime("%d-%m-%Y")
            time_str = dt.strftime("%H:%M")
            end = ev.get("end", {})
            if "dateTime" in end:
                dt_end = datetime.fromisoformat(end["dateTime"]).astimezone(tz)
                time_str += f"–{dt_end.strftime('%H:%M')}"
        else:
            date_str = start.get("date", "?")
            time_str = "All day"
        lines.append(f"  • {date_str}  {time_str}  [{cal_label}] {summary}")

    return "\n".join(lines)


# ── Next upcoming event ───────────────────────────────────────────────────────

def get_next_events(service, cal_key: str | None, limit: int = 1) -> list[dict]:
    """
    Return the next `limit` upcoming events from a specific calendar (cal_key)
    or across all calendars (cal_key=None).
    """
    tz = utils.TZ
    today = utils._today_local()
    end = today + timedelta(days=365)
    time_min = tz.localize(datetime(today.year, today.month, today.day, 0, 0, 0)).isoformat()
    time_max = tz.localize(datetime(end.year, end.month, end.day, 23, 59, 59)).isoformat()

    calendars = (
        {cal_key: config.CALENDARS[cal_key]} if cal_key else config.CALENDARS
    )

    all_events: list[dict] = []
    for name, cal_id in calendars.items():
        try:
            result = (
                service.events()
                .list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=limit if cal_key else 5,
                )
                .execute()
            )
            for event in result.get("items", []):
                event["_calendar_name"] = config.CALENDAR_DISPLAY_NAMES.get(name, name)
                all_events.append(event)
        except HttpError as e:
            print(f"[GCal] Error reading calendar '{name}': {e}")

    def sort_key(ev):
        start = ev.get("start", {})
        return start.get("dateTime", start.get("date", ""))

    all_events.sort(key=sort_key)
    return all_events[:limit]


def get_upcoming_events(service, cal_key: str | None, limit: int = 10) -> list[dict]:
    """
    Return the next `limit` upcoming events from a specific calendar (cal_key)
    or across all calendars (cal_key=None), sorted by start time.
    Searches up to 1 year ahead.
    """
    tz = utils.TZ
    today = utils._today_local()
    end = today + timedelta(days=365)
    time_min = tz.localize(datetime(today.year, today.month, today.day, 0, 0, 0)).isoformat()
    time_max = tz.localize(datetime(end.year, end.month, end.day, 23, 59, 59)).isoformat()

    calendars = (
        {cal_key: config.CALENDARS[cal_key]} if cal_key else config.CALENDARS
    )

    all_events: list[dict] = []
    # Request enough per calendar to ensure we get the global top `limit` after sorting
    per_cal = limit if cal_key else limit * len(config.CALENDARS)
    for name, cal_id in calendars.items():
        try:
            result = (
                service.events()
                .list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=per_cal,
                )
                .execute()
            )
            for event in result.get("items", []):
                event["_calendar_name"] = config.CALENDAR_DISPLAY_NAMES.get(name, name)
                all_events.append(event)
        except HttpError as e:
            print(f"[GCal] Error reading calendar '{name}': {e}")

    def sort_key(ev):
        start = ev.get("start", {})
        return start.get("dateTime", start.get("date", ""))

    all_events.sort(key=sort_key)
    return all_events[:limit]


def format_upcoming_events(events: list[dict], cal_key: str | None, limit: int) -> str:
    """Format upcoming events — grouped by date, each line shows time + calendar + title."""
    if not events:
        label = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key) if cal_key else "any calendar"
        return f"No upcoming events in {label}."

    tz = utils.TZ
    label = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key) if cal_key else "All calendars"
    lines = [f"<b>Upcoming ({label}, next {limit}):</b>"]

    # Group by date
    from datetime import date as date_type
    by_date: dict = {}
    for ev in events:
        start = ev.get("start", {})
        if "dateTime" in start:
            d = datetime.fromisoformat(start["dateTime"]).astimezone(tz).date()
        else:
            d = date_type.fromisoformat(start["date"])
        if d not in by_date:
            by_date[d] = []
        by_date[d].append(ev)

    for d, day_events in by_date.items():
        lines.append(f"\n<b>{d.strftime('%a %d-%m-%Y')}</b>")
        for ev in day_events:
            start = ev.get("start", {})
            cal_name = ev.get("_calendar_name", "")
            summary = ev.get("summary", "(no title)")
            if "dateTime" in start:
                dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
                time_str = dt.strftime("%H:%M")
                end_obj = ev.get("end", {})
                if "dateTime" in end_obj:
                    dt_end = datetime.fromisoformat(end_obj["dateTime"]).astimezone(tz)
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
    for ev in events:
        start = ev.get("start", {})
        cal_name = ev.get("_calendar_name", "")
        summary = ev.get("summary", "(no title)")
        if "dateTime" in start:
            dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
            date_str = dt.strftime("%d-%m-%Y")
            time_str = dt.strftime("%H:%M")
            end_obj = ev.get("end", {})
            if "dateTime" in end_obj:
                dt_end = datetime.fromisoformat(end_obj["dateTime"]).astimezone(tz)
                time_str += f"–{dt_end.strftime('%H:%M')}"
        else:
            date_str = start.get("date", "?")
            time_str = "All day"
        lines.append(f"  • {date_str}  {time_str}  [{cal_name}] {summary}")

    return "\n".join(lines)
    if getattr(service, "backend", None) == "local":
        return local_calendar_backend.list_events(service, target_date)

    if getattr(service, "backend", None) == "local":
        return local_calendar_backend.add_event(service, cmd)

    if getattr(service, "backend", None) == "local":
        return local_calendar_backend.delete_recurring_series(service, cal_key, title)

    if getattr(service, "backend", None) == "local":
        return local_calendar_backend.find_and_edit_event(service, cal_key, target_date, title, changes)

    if getattr(service, "backend", None) == "local":
        return local_calendar_backend.find_and_delete_event(service, cal_key, target_date, title)

    if getattr(service, "backend", None) == "local":
        return local_calendar_backend.search_events(service, keyword, days)

    if getattr(service, "backend", None) == "local":
        return local_calendar_backend.get_next_events(service, cal_key, limit)

    if getattr(service, "backend", None) == "local":
        return local_calendar_backend.get_upcoming_events(service, cal_key, limit)
