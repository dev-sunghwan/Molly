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
    Returns a confirmation string to send back via Telegram.
    """
    cal_id = config.CALENDARS[cmd["calendar"]]
    start_dt = utils.make_datetime(cmd["date"], cmd["start"])
    end_dt   = utils.make_datetime(cmd["date"], cmd["end"])

    event_body = {
        "summary": cmd["title"],
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": config.TIMEZONE,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": config.TIMEZONE,
        },
    }

    try:
        created = service.events().insert(calendarId=cal_id, body=event_body).execute()
        date_str = cmd["date"].strftime("%d-%m-%Y")
        cal_display = config.CALENDAR_DISPLAY_NAMES.get(cmd["calendar"], cmd["calendar"])
        return (
            f"✅ Added to {cal_display}:\n"
            f"  {cmd['title']}\n"
            f"  {date_str}  {cmd['start']}–{cmd['end']}"
        )
    except HttpError as e:
        return f"❌ Failed to add event: {e}"


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
