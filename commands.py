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
    "  add <calendar> <title> <date> <time>\n"
    "  add <calendar> <title> <time>      (date defaults to today)\n"
    "    calendar : " + ", ".join(config.VALID_CALENDAR_NAMES) + "\n"
    "    date     : today | tomorrow | Mon-Sun | DD-MM-YYYY\n"
    "    time     : HH:MM-HH:MM  or  HH:MM (default +1h)\n"
    "\n"
    "  delete <calendar> <date> <title>  — delete an event\n"
    "\n"
    "Examples:\n"
    "  add YounHa tennis tomorrow 17:00-18:00\n"
    "  add SungHwan dentist 14:00\n"
    "  delete SungHwan today dentist\n"
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

    # ── date-only query: Mon-Sun or DD-MM-YYYY ────────────────────────────────
    maybe_date = utils.parse_date(lower)
    if maybe_date is not None:
        return {"cmd": "date", "date": maybe_date}

    # ── unrecognised ──────────────────────────────────────────────────────────
    return {"error": USAGE}


def _parse_add(text: str) -> dict:
    """
    Parse the 'add' command.
    Layout with date:    add <calendar> <title...> <date> <time>
    Layout without date: add <calendar> <title...> <time>   (defaults to today)
    """
    rest = text[4:].strip()
    tokens = rest.split()

    # Minimum: calendar title time → 3 tokens
    if len(tokens) < 3:
        return {
            "error": (
                "❌ Not enough arguments.\n\n"
                "Usage: add <calendar> <title> <date> <time>\n"
                "   or: add <calendar> <title> <time>  (defaults to today)\n"
                "Example: add YounHa tennis tomorrow 17:00-18:00\n"
                "Example: add SungHwan dentist 14:00"
            )
        }

    cal_token = tokens[0]
    time_token = tokens[-1]

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

    # ── Determine date and title ──────────────────────────────────────────────
    # If tokens[-2] parses as a date, use it; otherwise default to today.
    if len(tokens) >= 4 and utils.parse_date(tokens[-2]) is not None:
        event_date = utils.parse_date(tokens[-2])
        title_tokens = tokens[1:-2]
    else:
        event_date = utils._today_local()
        title_tokens = tokens[1:-1]

    title = " ".join(title_tokens).strip()

    # ── Validate title ────────────────────────────────────────────────────────
    if not title:
        return {"error": "❌ Event title cannot be empty.\nUsage: add <calendar> <title> <time>"}

    # ── Validate time ─────────────────────────────────────────────────────────
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
        "date": event_date,
        "start": start_time,
        "end": end_time,
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
