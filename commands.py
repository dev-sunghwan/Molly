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

# ── Help strings ─────────────────────────────────────────────────────────────

# Short overview shown for unrecognised input or /help
USAGE = (
    "📅 Molly\n"
    "\n"
    "── View ──\n"
    "today · tomorrow\n"
    "week · week next\n"
    "month · month next\n"
    "&lt;Mon-Sun&gt; · &lt;dd-mm-yyyy&gt;\n"
    "\n"
    "── Commands ──\n"
    "add · edit · delete · delete all\n"
    "search · next · upcoming\n"
    "\n"
    "── Help ──\n"
    "help view · help add · help edit\n"
    "help delete · help search · help calendars"
)

# Detailed per-command help
HELP_VIEW = (
    "📅 View events\n"
    "\n"
    "Show events for a specific period:\n"
    "  today · tomorrow\n"
    "  week · week next\n"
    "  month · month next\n"
    "\n"
    "Show events for a specific day:\n"
    "  &lt;Mon-Sun&gt;      next occurrence of that weekday\n"
    "  &lt;dd-mm-yyyy&gt;   specific date\n"
    "\n"
    "e.g.  Fri\n"
    "      Sat\n"
    "      15-04-2026"
)

HELP_ADD = (
    "➕ Add an event\n"
    "\n"
    "add &lt;calendar&gt; &lt;title&gt; &lt;date&gt; &lt;time&gt;\n"
    "\n"
    "date and time are both optional:\n"
    "  omit date  → today\n"
    "  omit time  → all-day event\n"
    "  omit both  → all-day event today\n"
    "\n"
    "For a multi-day event, use 'to':\n"
    "  add &lt;calendar&gt; &lt;title&gt; &lt;date&gt; to &lt;date&gt;\n"
    "\n"
    "For a weekly recurring event, use 'every':\n"
    "  add &lt;calendar&gt; &lt;title&gt; every &lt;day&gt; &lt;time&gt;\n"
    "\n"
    "date  :  today · tomorrow · &lt;Mon-Sun&gt; · &lt;dd-mm-yyyy&gt;\n"
    "time  :  HH:MM-HH:MM  or  HH:MM  (end defaults to +1h)\n"
    "\n"
    "e.g.  add YounHa tennis tomorrow 17:00-18:00\n"
    "      add SungHwan dentist 14:00\n"
    "      add Family BBQ Sat\n"
    "      add HaNeul summer camp 14-07-2026 to 18-07-2026\n"
    "      add YounHa tennis every Mon 17:00-18:00\n"
    "      add HaNeul swimming every Wed"
)

HELP_EDIT = (
    "✏️ Edit an event\n"
    "\n"
    "edit &lt;calendar&gt; &lt;title&gt; time &lt;new_time&gt;\n"
    "edit &lt;calendar&gt; &lt;title&gt; date &lt;new_date&gt;\n"
    "edit &lt;calendar&gt; &lt;title&gt; title &lt;new_title&gt;\n"
    "\n"
    "Molly searches the next 90 days by title.\n"
    "To narrow to a specific day, add a date after the calendar:\n"
    "  edit &lt;calendar&gt; &lt;date&gt; &lt;title&gt; ...\n"
    "\n"
    "e.g.  edit SungHwan dentist time 15:00-16:00\n"
    "      edit YounHa tennis date Sat\n"
    "      edit Family BBQ title Family Picnic\n"
    "      edit SungHwan today dentist time 15:00"
)

HELP_DELETE = (
    "🗑 Delete an event\n"
    "\n"
    "delete &lt;calendar&gt; &lt;title&gt;\n"
    "\n"
    "Molly searches the next 90 days by title.\n"
    "To narrow to a specific day, add a date after the calendar:\n"
    "  delete &lt;calendar&gt; &lt;date&gt; &lt;title&gt;\n"
    "\n"
    "If multiple events match, Molly lists them\n"
    "and asks you to include a date.\n"
    "\n"
    "To delete an entire recurring series:\n"
    "  delete all &lt;calendar&gt; &lt;title&gt;\n"
    "\n"
    "e.g.  delete YounHa tennis\n"
    "      delete SungHwan today dentist\n"
    "      delete Family 25-12-2026 Christmas dinner\n"
    "      delete all YounHa tennis"
)

HELP_SEARCH = (
    "🔍 Search & browse\n"
    "\n"
    "Search by keyword (next 90 days):\n"
    "  search &lt;keyword&gt;\n"
    "\n"
    "Show the very next upcoming event:\n"
    "  next                  across all calendars\n"
    "  next &lt;calendar&gt;       for one person\n"
    "\n"
    "Show multiple upcoming events:\n"
    "  upcoming              next 10 events, all calendars\n"
    "  upcoming &lt;calendar&gt;   next 10 events for one person\n"
    "  upcoming &lt;calendar&gt; &lt;n&gt;   next N events (max 50)\n"
    "\n"
    "e.g.  search tennis\n"
    "      next YounHa\n"
    "      upcoming SungHwan\n"
    "      upcoming Family 20"
)

HELP_CALENDARS = (
    "📋 Calendars\n"
    "\n"
    + "\n".join(f"  {name}" for name in config.VALID_CALENDAR_NAMES) + "\n"
    + "\n"
    "Use the calendar name exactly as shown above\n"
    "(not case-sensitive).\n"
    "\n"
    "e.g.  add YounHa tennis tomorrow 17:00-18:00\n"
    "      upcoming SungHwan\n"
    "      delete Family BBQ"
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

    # ── help ─────────────────────────────────────────────────────────────────
    if lower in ("help", "/help"):
        return {"cmd": "help", "topic": None}

    if lower.startswith("help "):
        topic = lower[5:].strip()
        return {"cmd": "help", "topic": topic}

    # ── today / tomorrow / week / month ──────────────────────────────────────
    if lower == "today":
        return {"cmd": "today"}

    if lower == "tomorrow":
        return {"cmd": "tomorrow"}

    if lower == "week":
        return {"cmd": "week"}

    if lower == "week next":
        return {"cmd": "week_next"}

    if lower == "month":
        return {"cmd": "month"}

    if lower == "month next":
        return {"cmd": "month_next"}

    if lower == "next":
        return {"cmd": "next", "calendar": None}

    # ── add / delete / edit / search / next <cal> ────────────────────────────
    if lower.startswith("add "):
        return _parse_add(text)

    if lower.startswith("delete all "):
        return _parse_delete_all(text)

    if lower.startswith("delete "):
        return _parse_delete(text)

    if lower.startswith("edit "):
        return _parse_edit(text)

    if lower.startswith("search "):
        keyword = text[7:].strip()
        if not keyword:
            return {"error": "❌ Search keyword cannot be empty.\nUsage: search <keyword>"}
        return {"cmd": "search", "keyword": keyword}

    if lower.startswith("next "):
        cal_token = text[5:].strip()
        cal_key = cal_token.lower()
        if cal_key not in config.CALENDARS:
            valid = ", ".join(config.VALID_CALENDAR_NAMES)
            return {
                "error": (
                    f"❌ Unknown calendar: '{cal_token}'\n"
                    f"Valid calendars: {valid}\n"
                    f"Or use 'next' alone to see next event across all calendars."
                )
            }
        return {"cmd": "next", "calendar": cal_key}

    if lower == "upcoming":
        return {"cmd": "upcoming", "calendar": None, "limit": 10}

    if lower.startswith("upcoming "):
        return _parse_upcoming(text)

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

    # ── Detect multi-day: "to" keyword between two dates ─────────────────────
    if "to" in lower_tokens:
        to_idx = lower_tokens.index("to")
        # "to" must not be first or last, and neighbours must be dates
        if 0 < to_idx < len(tokens) - 1:
            start_date = utils.parse_date(tokens[to_idx - 1].lower())
            end_date   = utils.parse_date(tokens[to_idx + 1].lower())
            if start_date is not None and end_date is not None:
                title_tokens = tokens[1:to_idx - 1]
                title = " ".join(title_tokens).strip()
                if not title:
                    return {"error": "❌ Event title cannot be empty.\nExample: add HaNeul summer camp 14-07-2026 to 18-07-2026"}
                if end_date < start_date:
                    return {"error": "❌ End date cannot be before start date."}
                return {
                    "cmd": "add",
                    "calendar": cal_key,
                    "calendar_display": cal_token,
                    "title": title,
                    "date": start_date,
                    "end_date": end_date,
                    "all_day": True,
                }

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

    # Scan title tokens for an embedded date (e.g. user puts date after title)
    # First date found is used as the search date; remaining tokens form the title.
    title_tokens_raw = tokens[title_start:field_idx]
    embedded_date = None
    clean_title_tokens = []
    for tok in title_tokens_raw:
        if embedded_date is None:
            parsed = utils.parse_date(tok.lower())
            if parsed is not None:
                embedded_date = parsed
                continue  # exclude this token from the title
        clean_title_tokens.append(tok)

    if embedded_date is not None:
        event_date = embedded_date

    event_title = " ".join(clean_title_tokens).strip()
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


def _parse_upcoming(text: str) -> dict:
    """
    Parse: upcoming [<calendar>] [<n>]

    upcoming YounHa      → next 10 events for YounHa
    upcoming YounHa 20   → next 20 events for YounHa
    upcoming 20          → next 20 events across all calendars
    """
    rest = text[9:].strip()  # len("upcoming ") == 9
    tokens = rest.split()

    cal_key = None
    limit = 10

    if not tokens:
        return {"cmd": "upcoming", "calendar": None, "limit": 10}

    # Check if first token is a number
    if tokens[0].isdigit():
        limit = min(int(tokens[0]), 50)
        return {"cmd": "upcoming", "calendar": None, "limit": limit}

    # First token should be a calendar name
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

    # Optional second token: limit
    if len(tokens) >= 2:
        if tokens[1].isdigit():
            limit = min(int(tokens[1]), 50)
        else:
            return {
                "error": (
                    f"❌ Expected a number after '{cal_token}', got '{tokens[1]}'\n"
                    "Example: upcoming YounHa 20"
                )
            }

    return {"cmd": "upcoming", "calendar": cal_key, "limit": limit}


def _parse_delete_all(text: str) -> dict:
    """Parse: delete all <calendar> <title> — deletes entire recurring series."""
    rest = text[11:].strip()  # len("delete all ") == 11
    tokens = rest.split()

    if len(tokens) < 2:
        return {
            "error": (
                "❌ Not enough arguments.\n\n"
                "Usage: delete all <calendar> <title>\n"
                "Example: delete all YounHa tennis"
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

    title = " ".join(tokens[1:])
    return {
        "cmd": "delete_all",
        "calendar": cal_key,
        "title": title,
    }


def _parse_delete(text: str) -> dict:
    """
    Parse: delete <calendar> [<date>] <title>

    Date is optional. If the second token parses as a date it is used to
    narrow the search; otherwise the title search spans the next 90 days.
    """
    rest = text[7:].strip()  # len("delete ") == 7
    tokens = rest.split()

    if len(tokens) < 2:
        return {
            "error": (
                "❌ Not enough arguments.\n\n"
                "Usage: delete <calendar> <date> <title>\n"
                "   or: delete <calendar> <title>  (search next 90 days)\n"
                "Example: delete SungHwan today dentist\n"
                "Example: delete SungHwan dentist"
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

    # ── Optional date: check if tokens[1] is a date ───────────────────────────
    maybe_date = utils.parse_date(tokens[1].lower())
    if maybe_date is not None:
        if len(tokens) < 3:
            return {"error": "❌ Event title cannot be empty.\nUsage: delete <calendar> <date> <title>"}
        event_date = maybe_date
        title = " ".join(tokens[2:])
    else:
        event_date = None  # search upcoming 90 days
        title = " ".join(tokens[1:])

    if not title:
        return {"error": "❌ Event title cannot be empty."}

    return {
        "cmd": "delete",
        "calendar": cal_key,
        "date": event_date,
        "title": title,
    }
