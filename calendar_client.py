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
                event["_calendar_name"] = name.capitalize()
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
        cal_display = cmd.get("calendar_display", cmd["calendar"]).capitalize()
        return (
            f"✅ Added to {cal_display}:\n"
            f"  {cmd['title']}\n"
            f"  {date_str}  {cmd['start']}–{cmd['end']}"
        )
    except HttpError as e:
        return f"❌ Failed to add event: {e}"
