"""
google_calendar_backend.py — Google Calendar execution backend.

This module contains the concrete Google Calendar implementation used by the
backend-agnostic calendar repository layer.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config
import utils

SCOPES = ["https://www.googleapis.com/auth/calendar"]


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

        config.TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=creds)


def list_events_range(service, start_date: date, end_date: date) -> list[dict]:
    """Return all events from start_date to end_date (inclusive) across all calendars."""
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

    all_events.sort(key=_sort_key)
    return all_events


def list_events(service, target_date: date) -> list[dict]:
    """Return all events on target_date across all calendars, sorted by start time."""
    return list_events_range(service, target_date, target_date)


def add_event(service, cmd: dict) -> str:
    """
    Insert an event into the specified calendar.
    Supports timed events, all-day events, and weekly recurring events.
    """
    cal_id = config.CALENDARS[cmd["calendar"]]
    cal_display = config.CALENDAR_DISPLAY_NAMES.get(cmd["calendar"], cmd["calendar"])
    all_day = cmd.get("all_day", False)

    if all_day:
        start_date_str = cmd["date"].strftime("%Y-%m-%d")
        if "end_date" in cmd:
            end_date_exclusive = cmd["end_date"] + timedelta(days=1)
            end_date_str = end_date_exclusive.strftime("%Y-%m-%d")
            reply_time_str = (
                f"All day  ({utils.format_short_day_date(cmd['date'])} – "
                f"{utils.format_short_day_date(cmd['end_date'])})"
            )
        else:
            end_date_str = start_date_str
            reply_time_str = "All day"
        event_body = {
            "summary": cmd["title"],
            "start": {"date": start_date_str},
            "end": {"date": end_date_str},
        }
    else:
        start_dt = utils.make_datetime(cmd["date"], cmd["start"])
        end_dt = utils.make_datetime(cmd.get("end_date", cmd["date"]), cmd["end"])
        event_body = {
            "summary": cmd["title"],
            "start": {"dateTime": start_dt.isoformat(), "timeZone": config.TIMEZONE},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": config.TIMEZONE},
        }
        if cmd.get("end_date") and cmd["end_date"] != cmd["date"]:
            reply_time_str = (
                f"{utils.format_short_day_date(cmd['date'])} {cmd['start']} – "
                f"{utils.format_short_day_date(cmd['end_date'])} {cmd['end']}"
            )
        else:
            reply_time_str = f"{cmd['start']}–{cmd['end']}"

    if "recurrence" in cmd:
        event_body["recurrence"] = cmd["recurrence"]

    try:
        service.events().insert(calendarId=cal_id, body=event_body).execute()
        date_str_display = utils.format_short_day_date(cmd["date"])
        recurring_label = "  (weekly recurring)" if "recurrence" in cmd else ""
        reply = (
            f"✅ Added to {cal_display}:\n"
            f"  {cmd['title']}\n"
            f"  {date_str_display}  {reply_time_str}{recurring_label}"
        )
        if not all_day:
            conflicts = _find_conflicts(
                service,
                cal_id,
                cmd["date"],
                cmd["start"],
                cmd["end"],
                cmd["title"],
            )
            if conflicts:
                tz = utils.TZ
                lines = ["\n⚠️ Conflicts in same calendar:"]
                for event in conflicts:
                    start = event.get("start", {})
                    end = event.get("end", {})
                    dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
                    dt_end = datetime.fromisoformat(end["dateTime"]).astimezone(tz)
                    lines.append(
                        f"  • {dt.strftime('%H:%M')}–{dt_end.strftime('%H:%M')}  {event.get('summary', '')}"
                    )
                reply += "\n".join(lines)
        return reply
    except HttpError as e:
        return f"❌ Failed to add event: {e}"


def delete_recurring_series(service, cal_key: str, title: str) -> str:
    """
    Find a recurring event by title and delete the entire series (master event).
    Searches the next 90 days for an instance, then deletes the master.
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
        matches = [event for event in events if event.get("summary", "").lower() == title.lower()]

        if not matches:
            return f"❌ No event '{title}' found in {cal_display} (next 90 days)"

        if len(matches) > 1:
            lines = [
                f"❌ Multiple events named '{title}' in {cal_display}. Nothing deleted. Specify with 'delete':\n"
            ]
            seen = set()
            for event in matches:
                master_id = event.get("recurringEventId", event.get("id", ""))
                if master_id in seen:
                    continue
                seen.add(master_id)
                start = event.get("start", {})
                if "dateTime" in start:
                    dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
                    lines.append(
                        f"  • {dt.strftime('%d-%m-%Y')}  {dt.strftime('%H:%M')}  {event.get('summary')}"
                    )
                else:
                    lines.append(f"  • {start.get('date', '?')}  All day  {event.get('summary')}")
            return "\n".join(lines)

        event = matches[0]
        recurring_event_id = event.get("recurringEventId")

        if recurring_event_id:
            service.events().delete(calendarId=cal_id, eventId=recurring_event_id).execute()
            return f"Deleted entire series from {cal_display}:\n  {title}"

        service.events().delete(calendarId=cal_id, eventId=event["id"]).execute()
        return (
            f"Deleted from {cal_display}:\n"
            f"  {title}\n  (not a recurring event — single occurrence deleted)"
        )
    except HttpError as e:
        return f"❌ Failed to delete series: {e}"


def find_and_edit_event(service, cal_key: str, target_date: date | None, title: str, changes: dict) -> str:
    """Find an event by calendar and title, then apply changes."""
    cal_id = config.CALENDARS[cal_key]
    cal_display = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key)
    tz = utils.TZ

    if target_date is not None:
        time_min = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)).isoformat()
        time_max = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)).isoformat()
        search_desc = f"on {target_date.strftime('%d-%m-%Y')}"
    else:
        today = utils._today_local()
        end = today + timedelta(days=90)
        time_min = tz.localize(datetime(today.year, today.month, today.day, 0, 0, 0)).isoformat()
        time_max = tz.localize(datetime(end.year, end.month, end.day, 23, 59, 59)).isoformat()
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
        matches = []
        for event in events:
            if title and event.get("summary", "").lower() != title.lower():
                continue
            if start_time:
                start = event.get("start", {})
                if "dateTime" not in start:
                    continue
                dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
                if dt.strftime("%H:%M") != start_time:
                    continue
            matches.append(event)

        if not matches:
            if title and start_time:
                return f"❌ No event '{title}' at {start_time} found in {cal_display} {search_desc}"
            if title:
                return f"❌ No event '{title}' found in {cal_display} {search_desc}"
            if start_time:
                return f"❌ No event at {start_time} found in {cal_display} {search_desc}"
            return f"❌ No matching event found in {cal_display} {search_desc}"

        if len(matches) > 1:
            lines = [f"❌ Multiple events named '{title}' in {cal_display}. Nothing changed. Specify a date:\n"]
            for event in matches:
                start = event.get("start", {})
                if "dateTime" in start:
                    dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
                    lines.append(
                        f"  • {dt.strftime('%d-%m-%Y')}  {dt.strftime('%H:%M')}  {event.get('summary')}"
                    )
                else:
                    lines.append(f"  • {start.get('date', '?')}  All day  {event.get('summary')}")
            return "\n".join(lines)

        event = matches[0]
        existing_start = event.get("start", {})
        existing_end = event.get("end", {})
        is_all_day = "date" in existing_start
        update_body = dict(event)

        if "title" in changes:
            update_body["summary"] = changes["title"]

        if "date" in changes:
            new_date = changes["date"]
            if not is_all_day:
                old_start_dt = datetime.fromisoformat(existing_start["dateTime"]).astimezone(tz)
                old_end_dt = datetime.fromisoformat(existing_end["dateTime"]).astimezone(tz)
                new_start_dt = tz.localize(
                    datetime(new_date.year, new_date.month, new_date.day, old_start_dt.hour, old_start_dt.minute)
                )
                new_end_dt = tz.localize(
                    datetime(new_date.year, new_date.month, new_date.day, old_end_dt.hour, old_end_dt.minute)
                )
                update_body["start"] = {"dateTime": new_start_dt.isoformat(), "timeZone": config.TIMEZONE}
                update_body["end"] = {"dateTime": new_end_dt.isoformat(), "timeZone": config.TIMEZONE}
            else:
                update_body["start"] = {"date": new_date.strftime("%Y-%m-%d")}
                update_body["end"] = {"date": new_date.strftime("%Y-%m-%d")}

        if "start" in changes and "end" in changes:
            if is_all_day:
                event_date_obj = date.fromisoformat(existing_start["date"])
            else:
                event_date_obj = datetime.fromisoformat(existing_start["dateTime"]).astimezone(tz).date()

            new_start_dt = utils.make_datetime(event_date_obj, changes["start"])
            new_end_dt = utils.make_datetime(event_date_obj, changes["end"])
            update_body["start"] = {"dateTime": new_start_dt.isoformat(), "timeZone": config.TIMEZONE}
            update_body["end"] = {"dateTime": new_end_dt.isoformat(), "timeZone": config.TIMEZONE}

        if update_body == dict(event) and "title" not in changes:
            return "❌ No changes specified."

        service.events().update(calendarId=cal_id, eventId=event["id"], body=update_body).execute()

        new_title = changes.get("title", event.get("summary", title))
        new_date_d = changes.get("date", target_date)
        date_disp = new_date_d.strftime("%d-%m-%Y") if new_date_d else "?"

        if "start" in changes:
            time_disp = f"{changes['start']}–{changes['end']}"
        elif not is_all_day:
            old_dt = datetime.fromisoformat(existing_start["dateTime"]).astimezone(tz)
            old_end_dt = datetime.fromisoformat(existing_end["dateTime"]).astimezone(tz)
            time_disp = f"{old_dt.strftime('%H:%M')}–{old_end_dt.strftime('%H:%M')}"
        else:
            time_disp = "All day"

        if isinstance(date_disp, str):
            try:
                date_obj = datetime.strptime(date_disp, "%d-%m-%Y").date()
                date_disp = utils.format_short_day_date(date_obj)
            except ValueError:
                pass
        return f"✅ Updated in {cal_display}:\n  {new_title}\n  {date_disp}  {time_disp}"
    except HttpError as e:
        return f"❌ Failed to edit event: {e}"




def move_event(service, source_cal_key: str, target_cal_key: str, target_date: date | None, title: str) -> str:
    """Move one event between calendars while preserving title/date/time."""
    source_cal_id = config.CALENDARS[source_cal_key]
    source_display = config.CALENDAR_DISPLAY_NAMES.get(source_cal_key, source_cal_key)
    target_display = config.CALENDAR_DISPLAY_NAMES.get(target_cal_key, target_cal_key)
    tz = utils.TZ

    if target_date is not None:
        time_min = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)).isoformat()
        time_max = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)).isoformat()
        search_desc = f"on {target_date.strftime('%d-%m-%Y')}"
    else:
        today = utils._today_local()
        end = today + timedelta(days=90)
        time_min = tz.localize(datetime(today.year, today.month, today.day, 0, 0, 0)).isoformat()
        time_max = tz.localize(datetime(end.year, end.month, end.day, 23, 59, 59)).isoformat()
        search_desc = "in the next 90 days"

    try:
        result = (
            service.events()
            .list(
                calendarId=source_cal_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = result.get("items", [])
        matches = [event for event in events if event.get("summary", "").lower() == title.lower()]

        if not matches:
            return f"❌ No event '{title}' found in {source_display} {search_desc}"

        if len(matches) > 1:
            lines = [f"❌ Multiple events named '{title}' in {source_display}. Nothing moved. Specify a date:\n"]
            for event in matches:
                start = event.get("start", {})
                if "dateTime" in start:
                    dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
                    lines.append(f"  • {dt.strftime('%d-%m-%Y')}  {dt.strftime('%H:%M')}  {event.get('summary')}")
                else:
                    lines.append(f"  • {start.get('date', '?')}  All day  {event.get('summary')}")
            return "\n".join(lines)

        event = matches[0]
        new_body = {k: v for k, v in event.items() if k not in {"id", "etag", "htmlLink", "created", "updated", "iCalUID", "sequence", "organizer"}}
        created = service.events().insert(calendarId=config.CALENDARS[target_cal_key], body=new_body).execute()
        service.events().delete(calendarId=source_cal_id, eventId=event["id"]).execute()

        start = created.get("start", {})
        if "dateTime" in start:
            dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
            end = created.get("end", {})
            if "dateTime" in end:
                dt_end = datetime.fromisoformat(end["dateTime"]).astimezone(tz)
                time_disp = f"{dt.strftime('%H:%M')}–{dt_end.strftime('%H:%M')}"
            else:
                time_disp = dt.strftime('%H:%M')
            date_disp = utils.format_short_day_date(dt.date())
        else:
            date_disp = utils.format_short_day_date(date.fromisoformat(start.get("date", "1970-01-01")))
            time_disp = "All day"

        return f"✅ Moved from {source_display} to {target_display}:\n  {title}\n  {date_disp}  {time_disp}"
    except HttpError as e:
        return f"❌ Failed to move event: {e}"

def find_and_delete_event(service, cal_key: str, target_date: date | None, title: str | None, start_time: str | None = None) -> str:
    """Find an event by title in a specific calendar and delete it."""
    cal_id = config.CALENDARS[cal_key]
    cal_display = config.CALENDAR_DISPLAY_NAMES.get(cal_key, cal_key)
    tz = utils.TZ

    if target_date is not None:
        time_min = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)).isoformat()
        time_max = tz.localize(datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)).isoformat()
        search_desc = f"on {target_date.strftime('%d-%m-%Y')}"
    else:
        today = utils._today_local()
        end = today + timedelta(days=90)
        time_min = tz.localize(datetime(today.year, today.month, today.day, 0, 0, 0)).isoformat()
        time_max = tz.localize(datetime(end.year, end.month, end.day, 23, 59, 59)).isoformat()
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
        matches = []
        for event in events:
            if title and event.get("summary", "").lower() != title.lower():
                continue
            if start_time:
                start = event.get("start", {})
                if "dateTime" not in start:
                    continue
                dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
                if dt.strftime("%H:%M") != start_time:
                    continue
            matches.append(event)

        if not matches:
            if title and start_time:
                return f"❌ No event '{title}' at {start_time} found in {cal_display} {search_desc}"
            if title:
                return f"❌ No event '{title}' found in {cal_display} {search_desc}"
            if start_time:
                return f"❌ No event at {start_time} found in {cal_display} {search_desc}"
            return f"❌ No matching event found in {cal_display} {search_desc}"

        if len(matches) > 1:
            lines = [f"❌ Multiple events named '{title}' in {cal_display}. Nothing deleted. Specify a date:\n"]
            for event in matches:
                start = event.get("start", {})
                if "dateTime" in start:
                    dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
                    lines.append(
                        f"  • {dt.strftime('%d-%m-%Y')}  {dt.strftime('%H:%M')}  {event.get('summary')}"
                    )
                else:
                    lines.append(f"  • {start.get('date', '?')}  All day  {event.get('summary')}")
            return "\n".join(lines)

        event = matches[0]
        start = event.get("start", {})
        if "dateTime" in start:
            event_date_str = datetime.fromisoformat(start["dateTime"]).astimezone(tz).strftime("%d-%m-%Y")
        else:
            event_date_str = start.get("date", "?")
        service.events().delete(calendarId=cal_id, eventId=event["id"]).execute()
        return f"Deleted from {cal_display}:\n  {title}\n  {event_date_str}"
    except HttpError as e:
        return f"❌ Failed to delete event: {e}"


def search_events(service, keyword: str, days: int = 90) -> list[dict]:
    """Search for events containing keyword across all calendars in the next `days` days."""
    tz = utils.TZ
    today = utils._today_local()
    end = today + timedelta(days=days)
    time_min = tz.localize(datetime(today.year, today.month, today.day, 0, 0, 0)).isoformat()
    time_max = tz.localize(datetime(end.year, end.month, end.day, 23, 59, 59)).isoformat()
    keyword_lower = keyword.lower()

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
                    q=keyword,
                )
                .execute()
            )
            for event in result.get("items", []):
                if keyword_lower in event.get("summary", "").lower():
                    event["_calendar_name"] = config.CALENDAR_DISPLAY_NAMES.get(name, name)
                    all_events.append(event)
        except HttpError as e:
            print(f"[GCal] Error searching calendar '{name}': {e}")

    all_events.sort(key=_sort_key)
    return all_events


def get_next_events(service, cal_key: str | None, limit: int = 1) -> list[dict]:
    """Return the next `limit` upcoming events from one calendar or all calendars."""
    events = get_upcoming_events(service, cal_key, limit)
    return events[:limit]


def get_upcoming_events(service, cal_key: str | None, limit: int = 10) -> list[dict]:
    """Return the next `limit` upcoming events from one calendar or all calendars."""
    tz = utils.TZ
    today = utils._today_local()
    end = today + timedelta(days=365)
    time_min = tz.localize(datetime(today.year, today.month, today.day, 0, 0, 0)).isoformat()
    time_max = tz.localize(datetime(end.year, end.month, end.day, 23, 59, 59)).isoformat()
    calendars = {cal_key: config.CALENDARS[cal_key]} if cal_key else config.CALENDARS

    all_events: list[dict] = []
    per_calendar = limit if cal_key else limit * len(config.CALENDARS)
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
                    maxResults=per_calendar,
                )
                .execute()
            )
            for event in result.get("items", []):
                event["_calendar_name"] = config.CALENDAR_DISPLAY_NAMES.get(name, name)
                all_events.append(event)
        except HttpError as e:
            print(f"[GCal] Error reading calendar '{name}': {e}")

    all_events.sort(key=_sort_key)
    return all_events[:limit]


def _find_conflicts(service, cal_id: str, event_date, start_str: str, end_str: str, new_title: str) -> list[dict]:
    """Return existing timed events in cal_id that overlap with start_str–end_str on event_date."""
    tz = utils.TZ
    new_start = utils.make_datetime(event_date, start_str)
    new_end = utils.make_datetime(event_date, end_str)
    time_min = tz.localize(datetime(event_date.year, event_date.month, event_date.day, 0, 0, 0)).isoformat()
    time_max = tz.localize(datetime(event_date.year, event_date.month, event_date.day, 23, 59, 59)).isoformat()
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
    except HttpError:
        return []

    conflicts = []
    for event in result.get("items", []):
        start = event.get("start", {})
        if "dateTime" not in start:
            continue
        if event.get("summary", "") == new_title:
            continue
        event_start = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
        event_end = datetime.fromisoformat(event.get("end", {})["dateTime"]).astimezone(tz)
        if new_start < event_end and new_end > event_start:
            conflicts.append(event)
    return conflicts


def _sort_key(event: dict) -> str:
    start = event.get("start", {})
    return start.get("dateTime", start.get("date", ""))
