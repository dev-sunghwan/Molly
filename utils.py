"""
utils.py — Date/time parsing and Telegram reply formatting.

Date formats accepted (all British-style):
  - "today"
  - "tomorrow"
  - "Mon" / "Tue" / "Wed" / "Thu" / "Fri" / "Sat" / "Sun"  (next occurrence)
  - "DD-MM-YYYY"  e.g. "08-04-2026"

Time formats accepted:
  - "HH:MM-HH:MM"  e.g. "17:00-18:00"
  - "HH:MM"        e.g. "17:00"  (default duration: 1 hour)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytz

import config

# ── Timezone ──────────────────────────────────────────────────────────────────
TZ = pytz.timezone(config.TIMEZONE)

_DAY_NAMES = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}


# ── Date parsing ──────────────────────────────────────────────────────────────

def _today_local() -> date:
    return datetime.now(TZ).date()


def parse_date(token: str) -> date | None:
    """
    Parse a date token into a date object.
    Returns None if the token is unrecognised.
    """
    token = token.strip().lower()

    if token == "today":
        return _today_local()

    if token == "tomorrow":
        return _today_local() + timedelta(days=1)

    if token in _DAY_NAMES:
        today = _today_local()
        target_weekday = _DAY_NAMES[token]
        days_ahead = (target_weekday - today.weekday()) % 7
        # If today is that weekday, stay on today (days_ahead == 0)
        return today + timedelta(days=days_ahead)

    # DD-MM-YYYY
    try:
        return datetime.strptime(token, "%d-%m-%Y").date()
    except ValueError:
        pass

    return None


def parse_time(token: str) -> tuple[str, str] | None:
    """
    Parse a time token into (start_time, end_time) strings, both "HH:MM".
    Returns None if the token is unrecognised.
    Default duration when only start is given: 1 hour.
    """
    token = token.strip()

    if "-" in token:
        parts = token.split("-", 1)
        start, end = parts[0].strip(), parts[1].strip()
        if _valid_hhmm(start) and _valid_hhmm(end):
            return start, end
    elif _valid_hhmm(token):
        h, m = map(int, token.split(":"))
        end_h = (h + 1) % 24
        return token, f"{end_h:02d}:{m:02d}"

    return None


def _valid_hhmm(s: str) -> bool:
    try:
        h, m = s.split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except (ValueError, AttributeError):
        return False


def make_datetime(d: date, hhmm: str) -> datetime:
    """Combine a date and HH:MM string into a timezone-aware datetime."""
    h, m = map(int, hhmm.split(":"))
    return TZ.localize(datetime(d.year, d.month, d.day, h, m))


# ── Reply formatting ──────────────────────────────────────────────────────────

def format_date_header(d: date) -> str:
    """e.g.  📅 Tuesday, 08-04-2026"""
    return f"📅 {d.strftime('%A, %d-%m-%Y')}"


def format_event(event: dict) -> str:
    """Format a single Google Calendar event dict into a reply line."""
    start = event.get("start", {})
    summary = event.get("summary", "(no title)")
    cal_label = event.get("_calendar_name", "")

    # All-day event
    if "date" in start:
        time_str = "All day"
    else:
        dt = datetime.fromisoformat(start["dateTime"])
        dt_local = dt.astimezone(TZ)
        time_str = dt_local.strftime("%H:%M")

        end = event.get("end", {})
        if "dateTime" in end:
            dt_end = datetime.fromisoformat(end["dateTime"]).astimezone(TZ)
            time_str += f"–{dt_end.strftime('%H:%M')}"

    label = f"[{cal_label}] " if cal_label else ""
    return f"  • {time_str}  {label}{summary}"


def format_event_list(events: list[dict], d: date) -> str:
    """Build the full reply string for a list of events on a given date."""
    header = format_date_header(d)
    if not events:
        return f"{header}\n\nNo events."
    lines = [header, ""]
    for ev in events:
        lines.append(format_event(ev))
    return "\n".join(lines)
