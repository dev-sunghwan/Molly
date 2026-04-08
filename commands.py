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
    "Dobby commands:\n"
    "\n"
    "  today              — list today's events\n"
    "  tomorrow           — list tomorrow's events\n"
    "\n"
    "  add <calendar> <title> <date> <time>\n"
    "    calendar : " + ", ".join(config.VALID_CALENDAR_NAMES) + "\n"
    "    date     : today | tomorrow | Mon-Sun | DD-MM-YYYY\n"
    "    time     : HH:MM-HH:MM  or  HH:MM (default +1h)\n"
    "\n"
    "Examples:\n"
    "  add YounHa tennis tomorrow 17:00-18:00\n"
    "  add Family dinner Sat 19:00\n"
    "  add SungHwan meeting 15-04-2026 09:00-10:30"
)


def parse(text: str) -> dict:
    """
    Parse a message string and return a command dict.

    Success shapes:
      {"cmd": "today"}
      {"cmd": "tomorrow"}
      {"cmd": "add", "calendar": str, "title": str, "date": date, "start": str, "end": str}

    Failure shape:
      {"error": str}   — human-readable message to send back to the user
    """
    text = text.strip()
    lower = text.lower()

    # ── today / tomorrow ──────────────────────────────────────────────────────
    if lower == "today":
        return {"cmd": "today"}

    if lower == "tomorrow":
        return {"cmd": "tomorrow"}

    # ── add <calendar> <title> <date> <time> ─────────────────────────────────
    if lower.startswith("add "):
        return _parse_add(text)

    # ── unrecognised ──────────────────────────────────────────────────────────
    return {"error": USAGE}


def _parse_add(text: str) -> dict:
    """Parse the 'add' command. Expects at least 4 tokens after 'add'."""
    # Strip leading "add " (case-insensitive)
    rest = text[4:].strip()
    tokens = rest.split()

    # Minimum: calendar title date time → 4 tokens
    if len(tokens) < 4:
        return {
            "error": (
                "❌ Not enough arguments.\n\n"
                "Usage: add <calendar> <title> <date> <time>\n"
                "Example: add YounHa tennis tomorrow 17:00-18:00"
            )
        }

    # Token layout: [calendar] [title...] [date] [time]
    # date and time are always the last two tokens.
    cal_token = tokens[0]
    time_token = tokens[-1]
    date_token = tokens[-2]
    # Everything in between is the title (allows multi-word titles)
    title_tokens = tokens[1:-2]
    title = " ".join(title_tokens).strip()

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

    # ── Validate title ────────────────────────────────────────────────────────
    if not title:
        return {"error": "❌ Event title cannot be empty.\nUsage: add <calendar> <title> <date> <time>"}

    # ── Validate date ─────────────────────────────────────────────────────────
    event_date = utils.parse_date(date_token)
    if event_date is None:
        return {
            "error": (
                f"❌ Could not parse date: '{date_token}'\n"
                "Accepted formats: today, tomorrow, Mon-Sun, DD-MM-YYYY"
            )
        }

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
        "calendar": cal_key,           # lowercase key for CALENDARS lookup
        "calendar_display": cal_token, # original casing for display
        "title": title,
        "date": event_date,
        "start": start_time,
        "end": end_time,
    }
