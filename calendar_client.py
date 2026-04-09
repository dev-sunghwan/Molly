"""
calendar_client.py — All Google Calendar API interactions.

Public API:
  authenticate()          → builds and returns a GCal service object
  list_events(service, date)      → list[dict]  (events on that date, all calendars)
  add_event(service, cmd)         → str          (confirmation message)
"""
from __future__ import annotations

from datetime import date, datetime

import pytz
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config
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
        date_str = cmd["date"].strftime("%Y-%m-%d")
        event_body = {
            "summary": cmd["title"],
            "start": {"date": date_str},
            "end":   {"date": date_str},
        }
        reply_time_str = "All day"
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
        return (
            f"✅ Added to {cal_display}:\n"
            f"  {cmd['title']}\n"
            f"  {date_str_display}  {reply_time_str}{recurring_label}"
        )
    except HttpError as e:
        return f"❌ Failed to add event: {e}"


# ── Edit event ───────────────────────────────────────────────────────────────

def find_and_edit_event(service, cal_key: str, target_date: date, title: str, changes: dict) -> str:
    """
    Find an event by calendar, date, and title, then apply changes.

    changes keys (all optional):
      "start", "end"  — new time strings "HH:MM"
      "date"          — new date object (reschedule)
      "title"         — new title string

    - 0 matches → not found message
    - 1 match   → patched, confirmation
    - 2+ matches → list them, nothing changed
    """
    cal_id = config.CALENDARS[cal_key]
    cal_display = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key)
    date_str = target_date.strftime("%d-%m-%Y")
    tz = utils.TZ

    time_min = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)).isoformat()
    time_max = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)).isoformat()

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
            return f"❌ No event '{title}' found in {cal_display} on {date_str}"

        if len(matches) > 1:
            lines = [f"❌ Multiple events named '{title}' on {date_str} in {cal_display}. Nothing changed:"]
            for e in matches:
                start = e.get("start", {})
                if "dateTime" in start:
                    t = datetime.fromisoformat(start["dateTime"]).astimezone(tz).strftime("%H:%M")
                    lines.append(f"  • {t}  {e.get('summary')}")
                else:
                    lines.append(f"  • All day  {e.get('summary')}")
            return "\n".join(lines)

        event = matches[0]
        patch_body: dict = {}

        if "title" in changes:
            patch_body["summary"] = changes["title"]

        if "date" in changes:
            # Reschedule: move to new date, keep existing time if timed event
            new_date = changes["date"]
            existing_start = event.get("start", {})
            existing_end = event.get("end", {})

            if "dateTime" in existing_start:
                # Timed event — preserve the time, change the date
                old_start_dt = datetime.fromisoformat(existing_start["dateTime"]).astimezone(tz)
                old_end_dt   = datetime.fromisoformat(existing_end["dateTime"]).astimezone(tz)
                new_start_dt = tz.localize(datetime(new_date.year, new_date.month, new_date.day,
                                                     old_start_dt.hour, old_start_dt.minute))
                new_end_dt   = tz.localize(datetime(new_date.year, new_date.month, new_date.day,
                                                     old_end_dt.hour, old_end_dt.minute))
                patch_body["start"] = {"dateTime": new_start_dt.isoformat(), "timeZone": config.TIMEZONE}
                patch_body["end"]   = {"dateTime": new_end_dt.isoformat(),   "timeZone": config.TIMEZONE}
            else:
                # All-day event — just change the date
                patch_body["start"] = {"date": new_date.strftime("%Y-%m-%d")}
                patch_body["end"]   = {"date": new_date.strftime("%Y-%m-%d")}

        if "start" in changes and "end" in changes:
            # Change time — keep existing date
            existing_start = event.get("start", {})
            if "date" in existing_start:
                # Was all-day, now becoming timed
                event_date_obj = date.fromisoformat(existing_start["date"])
            else:
                event_date_obj = datetime.fromisoformat(existing_start["dateTime"]).astimezone(tz).date()

            new_start_dt = utils.make_datetime(event_date_obj, changes["start"])
            new_end_dt   = utils.make_datetime(event_date_obj, changes["end"])
            patch_body["start"] = {"dateTime": new_start_dt.isoformat(), "timeZone": config.TIMEZONE}
            patch_body["end"]   = {"dateTime": new_end_dt.isoformat(),   "timeZone": config.TIMEZONE}

        if not patch_body:
            return "❌ No changes specified."

        service.events().patch(calendarId=cal_id, eventId=event["id"], body=patch_body).execute()

        # Build confirmation message
        new_title   = changes.get("title", event.get("summary", title))
        new_date_d  = changes.get("date", target_date)
        date_disp   = new_date_d.strftime("%d-%m-%Y")

        if "start" in changes:
            time_disp = f"{changes['start']}–{changes['end']}"
        elif "dateTime" in event.get("start", {}):
            old_dt = datetime.fromisoformat(event["start"]["dateTime"]).astimezone(tz)
            old_end_dt = datetime.fromisoformat(event["end"]["dateTime"]).astimezone(tz)
            time_disp = f"{old_dt.strftime('%H:%M')}–{old_end_dt.strftime('%H:%M')}"
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

def find_and_delete_event(service, cal_key: str, target_date: date, title: str) -> str:
    """
    Find an event by title on a given date in a specific calendar and delete it.
    - 0 matches → not found message
    - 1 match   → deleted, confirmation
    - 2+ matches → list them, ask user to be more specific (nothing deleted)
    """
    cal_id = config.CALENDARS[cal_key]
    cal_display = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key)
    date_str = target_date.strftime("%d-%m-%Y")
    tz = utils.TZ

    time_min = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)).isoformat()
    time_max = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)).isoformat()

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
            return f"❌ No event '{title}' found in {cal_display} on {date_str}"

        if len(matches) > 1:
            lines = [f"❌ Multiple events named '{title}' on {date_str} in {cal_display}. Nothing deleted. Please specify:"]
            for e in matches:
                start = e.get("start", {})
                if "dateTime" in start:
                    t = datetime.fromisoformat(start["dateTime"]).astimezone(tz).strftime("%H:%M")
                    lines.append(f"  • {t}  {e.get('summary')}")
                else:
                    lines.append(f"  • All day  {e.get('summary')}")
            return "\n".join(lines)

        event = matches[0]
        service.events().delete(calendarId=cal_id, eventId=event["id"]).execute()
        return f"Deleted from {cal_display}:\n  {title}\n  {date_str}"

    except HttpError as e:
        return f"❌ Failed to delete event: {e}"
