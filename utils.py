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
from typing import Any

import pytz

import config

# ── Timezone ──────────────────────────────────────────────────────────────────
TZ = pytz.timezone(config.TIMEZONE)

_DAY_NAMES = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}

# Maps 3-letter day names to RFC 5545 BYDAY codes (for RRULE in recurring events)
_DAY_TO_RRULE = {
    "mon": "MO", "tue": "TU", "wed": "WE", "thu": "TH",
    "fri": "FR", "sat": "SA", "sun": "SU",
}


def day_name_to_rrule(day: str) -> str | None:
    """Convert a day name token (e.g. 'Mon', 'monday') to an RFC 5545 BYDAY code.
    Returns None if unrecognised."""
    return _DAY_TO_RRULE.get(day.strip().lower()[:3])


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
    """e.g.  📅 <b>Tuesday, 08-04-2026</b>"""
    return f"📅 <b>{d.strftime('%A, %d-%m-%Y')}</b>"


def format_event(event: dict, show_cal_label: bool = True) -> str:
    """Format a single Google Calendar event dict into a reply line."""
    start = event.get("start", {})
    summary = event.get("summary", "(no title)")
    cal_label = event.get("_calendar_name", "")

    # All-day event
    if "date" in start:
        start_d = date.fromisoformat(start["date"])
        end = event.get("end", {})
        if "date" in end:
            # Google end date is exclusive — subtract 1 day to get inclusive end
            end_d = date.fromisoformat(end["date"]) - timedelta(days=1)
            if end_d > start_d:
                time_str = f"All day  ({start_d.strftime('%d-%m')} – {end_d.strftime('%d-%m-%Y')})"
            else:
                time_str = "All day"
        else:
            time_str = "All day"
    else:
        dt = datetime.fromisoformat(start["dateTime"])
        dt_local = dt.astimezone(TZ)
        time_str = dt_local.strftime("%H:%M")

        end = event.get("end", {})
        if "dateTime" in end:
            dt_end = datetime.fromisoformat(end["dateTime"]).astimezone(TZ)
            time_str += f"–{dt_end.strftime('%H:%M')}"

    if show_cal_label and cal_label:
        return f"  • {time_str}  [{cal_label}] {summary}"
    return f"  • {time_str}  {summary}"


def format_event_list(events: list[dict], d: date) -> str:
    """Build the full reply string for a list of events on a given date.

    Events are grouped by calendar name. Within each calendar, events are
    sorted by start time (preserved from the input order).
    """
    header = format_date_header(d)
    if not events:
        return f"{header}\n\nNo events."

    # Group by calendar name, preserving insertion order
    by_cal: dict[str, list] = {}
    for ev in events:
        cal_name = ev.get("_calendar_name", "")
        if cal_name not in by_cal:
            by_cal[cal_name] = []
        by_cal[cal_name].append(ev)

    lines = [header]
    for cal_name, cal_events in by_cal.items():
        lines.append(f"\n<b>{cal_name}</b>")
        for ev in cal_events:
            lines.append(format_event(ev, show_cal_label=False))
    return "\n".join(lines)


def get_week_range() -> tuple[date, date]:
    """Return (monday, sunday) of the current week."""
    today = _today_local()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_next_week_range() -> tuple[date, date]:
    """Return (monday, sunday) of next week."""
    today = _today_local()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_month_range(offset: int = 0) -> tuple[date, date]:
    """Return (first_day, last_day) of the month at offset months from today.
    offset=0 → current month, offset=1 → next month.
    """
    today = _today_local()
    # Move forward by 'offset' months
    month = today.month + offset
    year = today.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    first = date(year, month, 1)
    # Last day: first day of next month minus one day
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return first, last


def format_week(events: list[dict], start_date: date, end_date: date) -> str:
    """Format events grouped by day for a week view."""
    by_date: dict[date, list[Any]] = {}
    for ev in events:
        start = ev.get("start", {})
        if "dateTime" in start:
            d = datetime.fromisoformat(start["dateTime"]).astimezone(TZ).date()
        else:
            d = date.fromisoformat(start["date"])
        if d not in by_date:
            by_date[d] = []
        by_date[d].append(ev)

    header = f"📅 <b>{start_date.strftime('%d-%m-%Y')} – {end_date.strftime('%d-%m-%Y')}</b>"
    lines = [header]

    current = start_date
    while current <= end_date:
        day_label = current.strftime("%a %d-%m")
        day_events = by_date.get(current, [])
        if day_events:
            lines.append(f"\n<b>{day_label}</b>")
            for ev in day_events:
                lines.append(format_event(ev))
        else:
            lines.append(f"\n<b>{day_label}</b>  —")
        current += timedelta(days=1)

    return "\n".join(lines)


def format_month(events: list[dict], first: date, last: date) -> str:
    """Format events grouped by day for a month view.
    Only days with events are shown (skips empty days for brevity).
    """
    by_date: dict[date, list[Any]] = {}
    for ev in events:
        start = ev.get("start", {})
        if "dateTime" in start:
            d = datetime.fromisoformat(start["dateTime"]).astimezone(TZ).date()
        else:
            d = date.fromisoformat(start["date"])
        if d not in by_date:
            by_date[d] = []
        by_date[d].append(ev)

    header = f"📅 <b>{first.strftime('%B %Y')}</b>"
    lines = [header]

    current = first
    while current <= last:
        day_events = by_date.get(current, [])
        if day_events:
            day_label = current.strftime("%a %d")
            lines.append(f"\n<b>{day_label}</b>")
            for ev in day_events:
                lines.append(format_event(ev))
        current += timedelta(days=1)

    if len(lines) == 1:
        lines.append("\nNo events.")

    return "\n".join(lines)
