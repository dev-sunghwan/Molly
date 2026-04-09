"""
commands.py — Parse raw Telegram message text into structured command dicts.

Supported commands:
  today
  tomorrow
  add <calendar> <title> <date> <time>

Returns a dict with key "cmd" and relevant fields, or a dict with "error" key.
"""
from __future__ import annotations

import config
import utils

# Help text sent on unrecognised input
USAGE = (
    "Molly commands:\n"
    "\n"
    "  today                        — today's events\n"
    "  tomorrow                     — tomorrow's events\n"
    "  week                         — this week's events\n"
    "  <date>                       — events on a specific date\n"
    "\n"
    "  add <calendar> <title> <date> <time>   — timed event\n"
    "  add <calendar> <title> <time>          — timed event (date = today)\n"
    "  add <calendar> <title> <date>          — all-day event\n"
    "  add <calendar> <title>                 — all-day event (today)\n"
    "  add <calendar> <title> every <day> <time>  — weekly recurring\n"
    "  add <calendar> <title> every <day>         — all-day weekly recurring\n"
    "    calendar : " + ", ".join(config.VALID_CALENDAR_NAMES) + "\n"
    "    date     : today | tomorrow | Mon-Sun | DD-MM-YYYY\n"
    "               Mon-Sun = next occurrence of that weekday (today if already that day)\n"
    "    time     : HH:MM-HH:MM  or  HH:MM (event duration defaults to +1h)\n"
    "               Times are in local time — DST is handled automatically\n"
    "\n"
    "  delete <calendar> <date> <title>        — delete an event\n"
    "  edit <calendar> <date> <title> time <new_time>   — change time\n"
    "  edit <calendar> <date> <title> date <new_date>   — reschedule\n"
    "  edit <calendar> <date> <title> title <new_title> — rename\n"
    "\n"
    "Examples:\n"
    "  add YounHa tennis tomorrow 17:00-18:00\n"
    "  add SungHwan dentist 14:00\n"
    "  add Family BBQ Sat                    (all-day, next Saturday)\n"
    "  add YounHa tennis every Mon 17:00-18:00\n"
    "  add HaNeul swimming every Wed         (all-day every Wednesday)\n"
    "  delete SungHwan today dentist\n"
    "  edit SungHwan today dentist time 15:00-16:00\n"
    "  edit YounHa tomorrow tennis date Sat\n"
    "  Fri\n"
    "  09-04-2026"
)


def parse(text: str) -> dict:
    """
    Parse a message string and return a command dict.

    Success shapes:
      {"cmd": "today"}
      {"cmd": "tomorrow"}
      {"cmd": "week"}
      {"cmd": "date",   "date": date}
      {"cmd": "add",    "calendar": str, "title": str, "date": date, "start": str, "end": str}
      {"cmd": "delete", "calendar": str, "date": date, "title": str}

    Failure shape:
      {"error": str}   — human-readable message to send back to the user
    """
    text = text.strip()
    lower = text.lower()

    # ── today / tomorrow / week ───────────────────────────────────────────────
    if lower == "today":
        return {"cmd": "today"}

    if lower == "tomorrow":
        return {"cmd": "tomorrow"}

    if lower == "week":
        return {"cmd": "week"}

    # ── add / delete ──────────────────────────────────────────────────────────
    if lower.startswith("add "):
        return _parse_add(text)

    if lower.startswith("delete "):
        return _parse_delete(text)

    if lower.startswith("edit "):
        return _parse_edit(text)

    # ── date-only query: Mon-Sun or DD-MM-YYYY ────────────────────────────────
    maybe_date = utils.parse_date(lower)
    if maybe_date is not None:
        return {"cmd": "date", "date": maybe_date}

    # ── unrecognised ──────────────────────────────────────────────────────────
    return {"error": USAGE}


def _parse_add(text: str) -> dict:
    """
    Parse the 'add' command.

    Supported layouts:
      add <cal> <title> <date> <time>   — timed event on a specific date
      add <cal> <title> <time>          — timed event today
      add <cal> <title> <date>          — all-day event on a specific date
      add <cal> <title>                 — all-day event today
      add <cal> <title> every <day> <time>  — weekly recurring timed event
      add <cal> <title> every <day>         — weekly recurring all-day event
    """
    rest = text[4:].strip()
    tokens = rest.split()

    # Need at minimum: calendar + title (2 tokens)
    if len(tokens) < 2:
        return {
            "error": (
                "❌ Not enough arguments.\n\n"
                "Usage: add <calendar> <title> <date> <time>\n"
                "   or: add <calendar> <title>  (all-day event today)\n"
                "Example: add YounHa tennis tomorrow 17:00-18:00\n"
                "Example: add Family BBQ Sat"
            )
        }

    cal_token = tokens[0]
    cal_key = cal_token.lower()

    # ── Validate calendar name ────────────────────────────────────────────────
    if cal_key not in config.CALENDARS:
        valid = ", ".join(config.VALID_CALENDAR_NAMES)
        return {
            "error": (
                f"❌ Unknown calendar: '{cal_token}'\n"
                f"Valid calendars: {valid}"
            )
        }

    # ── Detect recurring: "every" keyword ────────────────────────────────────
    lower_tokens = [t.lower() for t in tokens]
    if "every" in lower_tokens:
        return _parse_add_recurring(tokens, cal_key, cal_token)

    # ── Non-recurring: classify the last token ────────────────────────────────
    last = tokens[-1]
    last_is_time = utils.parse_time(last) is not None
    last_is_date = utils.parse_date(last.lower()) is not None

    if last_is_time:
        # Timed event — check if second-to-last token is a date
        if len(tokens) >= 4 and utils.parse_date(tokens[-2].lower()) is not None:
            event_date = utils.parse_date(tokens[-2].lower())
            title_tokens = tokens[1:-2]
        else:
            event_date = utils._today_local()
            title_tokens = tokens[1:-1]

        title = " ".join(title_tokens).strip()
        if not title:
            return {"error": "❌ Event title cannot be empty.\nUsage: add <calendar> <title> <time>"}

        start_time, end_time = utils.parse_time(last)
        return {
            "cmd": "add",
            "calendar": cal_key,
            "calendar_display": cal_token,
            "title": title,
            "date": event_date,
            "start": start_time,
            "end": end_time,
        }

    elif last_is_date:
        # All-day event on a specific date
        event_date = utils.parse_date(last.lower())
        title_tokens = tokens[1:-1]
        title = " ".join(title_tokens).strip()
        if not title:
            return {"error": "❌ Event title cannot be empty.\nUsage: add <calendar> <title> <date>"}
        return {
            "cmd": "add",
            "calendar": cal_key,
            "calendar_display": cal_token,
            "title": title,
            "date": event_date,
            "all_day": True,
        }

    elif len(tokens) == 2:
        # Only calendar + title → all-day event today
        title = tokens[1]
        return {
            "cmd": "add",
            "calendar": cal_key,
            "calendar_display": cal_token,
            "title": title,
            "date": utils._today_local(),
            "all_day": True,
        }

    else:
        return {
            "error": (
                f"❌ Could not parse time: '{last}'\n"
                "Accepted formats: HH:MM-HH:MM  or  HH:MM"
            )
        }


def _parse_add_recurring(tokens: list, cal_key: str, cal_token: str) -> dict:
    """
    Parse: add <cal> <title> every <day> [<time>]
    tokens[0] is the calendar (already validated by caller).
    """
    lower_tokens = [t.lower() for t in tokens]
    every_idx = lower_tokens.index("every")

    # Title is everything between calendar and "every"
    title_tokens = tokens[1:every_idx]
    title = " ".join(title_tokens).strip()
    if not title:
        return {"error": "❌ Event title cannot be empty before 'every'.\nExample: add YounHa tennis every Mon 17:00-18:00"}

    after_every = tokens[every_idx + 1:]
    if not after_every:
        return {"error": "❌ Expected a day name after 'every'.\nExample: add YounHa tennis every Mon 17:00-18:00"}

    day_token = after_every[0]
    rrule_day = utils.day_name_to_rrule(day_token)
    if rrule_day is None:
        return {
            "error": (
                f"❌ Unrecognised day name: '{day_token}'\n"
                "Use: Mon Tue Wed Thu Fri Sat Sun"
            )
        }

    # First occurrence = next occurrence of that weekday (reuses existing logic)
    first_date = utils.parse_date(day_token.lower())
    recurrence = [f"RRULE:FREQ=WEEKLY;BYDAY={rrule_day}"]

    if len(after_every) >= 2:
        # Timed recurring event
        time_token = after_every[-1]
        time_result = utils.parse_time(time_token)
        if time_result is None:
            return {
                "error": (
                    f"❌ Could not parse time: '{time_token}'\n"
                    "Accepted formats: HH:MM-HH:MM  or  HH:MM"
                )
            }
        start_time, end_time = time_result
        return {
            "cmd": "add",
            "calendar": cal_key,
            "calendar_display": cal_token,
            "title": title,
            "date": first_date,
            "start": start_time,
            "end": end_time,
            "recurrence": recurrence,
        }
    else:
        # All-day recurring event
        return {
            "cmd": "add",
            "calendar": cal_key,
            "calendar_display": cal_token,
            "title": title,
            "date": first_date,
            "all_day": True,
            "recurrence": recurrence,
        }


def _parse_edit(text: str) -> dict:
    """
    Parse: edit <calendar> [<date>] <title> <field> <new_value>

    Date is optional. If omitted, calendar_client will search upcoming events
    by title. If provided, it narrows the search to that specific date.

    Supported fields:
      time  <HH:MM-HH:MM | HH:MM>  — change start/end time
      date  <date>                  — reschedule to a new date
      title <new_title...>          — rename the event
    """
    rest = text[5:].strip()  # len("edit ") == 5
    tokens = rest.split()

    # Minimum: cal + title + field + value = 4 tokens
    if len(tokens) < 4:
        return {
            "error": (
                "❌ Not enough arguments.\n\n"
                "Usage:\n"
                "  edit <calendar> <title> time <new_time>\n"
                "  edit <calendar> <title> date <new_date>\n"
                "  edit <calendar> <title> title <new_title>\n"
                "  (optional) include date after calendar to narrow search:\n"
                "  edit <calendar> <date> <title> time <new_time>\n"
                "Example: edit SungHwan dentist time 15:00-16:00"
            )
        }

    cal_token = tokens[0]
    cal_key = cal_token.lower()

    if cal_key not in config.CALENDARS:
        valid = ", ".join(config.VALID_CALENDAR_NAMES)
        return {
            "error": (
                f"❌ Unknown calendar: '{cal_token}'\n"
                f"Valid calendars: {valid}"
            )
        }

    # Optional date: check if tokens[1] parses as a date
    maybe_date = utils.parse_date(tokens[1].lower())
    if maybe_date is not None:
        event_date = maybe_date
        title_start = 2
    else:
        event_date = None   # search upcoming events by title
        title_start = 1

    # Scan for the field keyword (time / date / title) from the right so that
    # multi-word event titles work correctly.
    field_keywords = {"time", "date", "title"}
    field_idx = None
    for i in range(len(tokens) - 1, title_start, -1):
        if tokens[i].lower() in field_keywords:
            field_idx = i
            break

    if field_idx is None or field_idx <= title_start:
        return {
            "error": (
                "❌ Missing field keyword.\n"
                "Specify what to change: time, date, or title\n"
                "Example: edit SungHwan dentist time 15:00"
            )
        }

    event_title = " ".join(tokens[title_start:field_idx]).strip()
    if not event_title:
        return {"error": "❌ Event title cannot be empty."}

    field = tokens[field_idx].lower()
    value_tokens = tokens[field_idx + 1:]
    if not value_tokens:
        return {"error": f"❌ No value provided after '{field}'."}

    changes: dict = {}

    if field == "time":
        time_token = value_tokens[0]
        time_result = utils.parse_time(time_token)
        if time_result is None:
            return {
                "error": (
                    f"❌ Could not parse time: '{time_token}'\n"
                    "Accepted formats: HH:MM-HH:MM  or  HH:MM"
                )
            }
        changes["start"], changes["end"] = time_result

    elif field == "date":
        new_date = utils.parse_date(value_tokens[0])
        if new_date is None:
            return {
                "error": (
                    f"❌ Could not parse new date: '{value_tokens[0]}'\n"
                    "Accepted formats: today, tomorrow, Mon-Sun, DD-MM-YYYY"
                )
            }
        changes["date"] = new_date

    elif field == "title":
        new_title = " ".join(value_tokens).strip()
        if not new_title:
            return {"error": "❌ New title cannot be empty."}
        changes["title"] = new_title

    return {
        "cmd": "edit",
        "calendar": cal_key,
        "date": event_date,   # None = search upcoming
        "title": event_title,
        "changes": changes,
    }


def _parse_delete(text: str) -> dict:
    """Parse: delete <calendar> <date> <title>"""
    rest = text[7:].strip()  # len("delete ") == 7
    tokens = rest.split()

    if len(tokens) < 3:
        return {
            "error": (
                "❌ Not enough arguments.\n\n"
                "Usage: delete <calendar> <date> <title>\n"
                "Example: delete SungHwan today dentist"
            )
        }

    cal_token = tokens[0]
    date_token = tokens[1]
    title = " ".join(tokens[2:])

    # ── Validate calendar name ────────────────────────────────────────────────
    cal_key = cal_token.lower()
    if cal_key not in config.CALENDARS:
        valid = ", ".join(config.VALID_CALENDAR_NAMES)
        return {
            "error": (
                f"❌ Unknown calendar: '{cal_token}'\n"
                f"Valid calendars: {valid}"
            )
        }

    # ── Validate date ─────────────────────────────────────────────────────────
    event_date = utils.parse_date(date_token)
    if event_date is None:
        return {
            "error": (
                f"❌ Could not parse date: '{date_token}'\n"
                "Accepted formats: today, tomorrow, Mon-Sun, DD-MM-YYYY"
            )
        }

    return {
        "cmd": "delete",
        "calendar": cal_key,
        "date": event_date,
        "title": title,
    }
