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

import re
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

_CALENDAR_LABELS = {
    "sunghwan": "성환",
    "jeeyoung": "지영",
    "younha": "윤하",
    "haneul": "하늘",
    "younho": "윤호",
    "family": "가족",
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
    token = token.strip("()[]{}.,")
    token = re.sub(r"(\d{1,2})(st|nd|rd|th)\b", r"\1", token)
    token = re.sub(r"\s+", " ", token.replace(",", " ")).strip()

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

    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            pass

    today = _today_local()
    for fmt in ("%d %B", "%d %b", "%B %d", "%b %d"):
        try:
            parsed = datetime.strptime(token, fmt).date().replace(year=today.year)
            return parsed
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
    token = token.replace("–", "-").replace("—", "-")
    token = re.sub(r"\b(?:bst|gmt|utc)\b", "", token, flags=re.IGNORECASE).strip()

    if "-" in token:
        start_raw, end_raw = [part.strip() for part in token.split("-", 1)]
        start = _parse_flexible_hhmm(start_raw)
        end = _parse_flexible_hhmm(end_raw, reference=start_raw if start else None)
        if start and end:
            return start, end
    else:
        parsed = _parse_flexible_hhmm(token)
        if parsed:
            h, m = map(int, parsed.split(":"))
            end_h = (h + 1) % 24
            return parsed, f"{end_h:02d}:{m:02d}"

    return None


def parse_clock_time(token: str) -> str | None:
    token = token.strip()
    if _valid_hhmm(token):
        return token
    parsed = _parse_flexible_hhmm(token)
    if parsed:
        return parsed
    return None


def _valid_hhmm(s: str) -> bool:
    try:
        h, m = s.split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except (ValueError, AttributeError):
        return False


def _parse_flexible_hhmm(token: str, reference: str | None = None) -> str | None:
    token = token.strip().lower().strip(".,")
    match = re.fullmatch(r"(\d{1,2})(?:(:|\.)(\d{2}))?\s*(am|pm)?", token)
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(3) or "00")
    meridiem = match.group(4)

    if meridiem is None and reference:
        ref_match = re.search(r"\b(am|pm)\b", reference.lower())
        if ref_match:
            meridiem = ref_match.group(1)

    if meridiem:
        if not 1 <= hour <= 12:
            return None
        if meridiem == "am":
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12

    if meridiem is None and not 0 <= hour <= 23:
        return None
    if not 0 <= minute <= 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def make_datetime(d: date, hhmm: str) -> datetime:
    """Combine a date and HH:MM string into a timezone-aware datetime."""
    h, m = map(int, hhmm.split(":"))
    return TZ.localize(datetime(d.year, d.month, d.day, h, m))


# ── Reply formatting ──────────────────────────────────────────────────────────

def format_date_header(d: date) -> str:
    """e.g.  📅 Wednesday, 08-04"""
    return f"📅 {d.strftime('%A, %d-%m')}"


def format_short_date(d: date) -> str:
    return d.strftime("%d-%m")


def format_short_day_date(d: date) -> str:
    return d.strftime("%a %d-%m")


def format_calendar_label(event: dict) -> str:
    cal_name = (event.get("_calendar_name") or "").strip()
    if not cal_name:
        return ""

    normalized = cal_name.lower()
    return _CALENDAR_LABELS.get(normalized, cal_name)


def event_display_summary(event: dict) -> str:
    summary = event.get("summary")
    if summary:
        return str(summary)
    override = event.get("_display_summary")
    if override:
        return str(override)
    return "(no title)"


    cal_name = (event.get("_calendar_name") or "").strip()
    if not cal_name:
        return ""

    normalized = cal_name.lower()
    return _CALENDAR_LABELS.get(normalized, cal_name)


def format_event(event: dict, show_cal_label: bool = True) -> str:
    """Format a single Google Calendar event dict into a reply line."""
    start = event.get("start", {})
    summary = event_display_summary(event)
    cal_label = format_calendar_label(event)

    # All-day event
    if "date" in start:
        start_d = date.fromisoformat(start["date"])
        end = event.get("end", {})
        if "date" in end:
            # Google end date is exclusive — subtract 1 day to get inclusive end
            end_d = date.fromisoformat(end["date"]) - timedelta(days=1)
            if end_d > start_d:
                time_str = f"All day  ({format_short_day_date(start_d)} – {format_short_day_date(end_d)})"
            else:
                time_str = "All day"
        else:
            time_str = "All day"
    else:
        dt = datetime.fromisoformat(start["dateTime"])
        dt_local = dt.astimezone(TZ)
        end = event.get("end", {})
        if "dateTime" in end:
            dt_end = datetime.fromisoformat(end["dateTime"]).astimezone(TZ)
            if dt_end.date() != dt_local.date():
                time_str = (
                    f"{format_short_day_date(dt_local.date())} {dt_local.strftime('%H:%M')} – "
                    f"{format_short_day_date(dt_end.date())} {dt_end.strftime('%H:%M')}"
                )
            else:
                time_str = f"{dt_local.strftime('%H:%M')}–{dt_end.strftime('%H:%M')}"
        else:
            time_str = dt_local.strftime("%H:%M")

    if show_cal_label and cal_label:
        return f"  • {time_str}  [{cal_label}] {summary}"
    return f"  • {time_str}  {summary}"


def format_event_list(events: list[dict], d: date) -> str:
    """Build the full reply string for a list of events on a given date."""
    header = format_date_header(d)
    if not events:
        return f"{header}\n\nNo events."

    lines = [header]
    for ev in events:
        lines.append(format_event(ev))
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
        for d in event_span_dates(ev):
            if d not in by_date:
                by_date[d] = []
            by_date[d].append(ev)

    header = f"📅 {format_short_day_date(start_date)} – {format_short_day_date(end_date)}"
    lines = [header]

    current = start_date
    while current <= end_date:
        day_label = current.strftime("%a %d-%m")
        day_events = by_date.get(current, [])
        if day_events:
            lines.append(f"\n{day_label}")
            for ev in day_events:
                lines.append(format_event(ev))
        else:
            lines.append(f"\n{day_label}  —")
        current += timedelta(days=1)

    return "\n".join(lines)


def format_month(events: list[dict], first: date, last: date) -> str:
    """Format events grouped by day for a month view.
    Only days with events are shown (skips empty days for brevity).
    """
    by_date: dict[date, list[Any]] = {}
    for ev in events:
        for d in event_span_dates(ev):
            if d not in by_date:
                by_date[d] = []
            by_date[d].append(ev)

    header = f"📅 {first.strftime('%B %Y')}"
    lines = [header]

    current = first
    while current <= last:
        day_events = by_date.get(current, [])
        if day_events:
            day_label = current.strftime("%a %d")
            lines.append(f"\n{day_label}")
            for ev in day_events:
                lines.append(format_event(ev))
        current += timedelta(days=1)

    if len(lines) == 1:
        lines.append("\nNo events.")

    return "\n".join(lines)


def event_span_dates(event: dict) -> list[date]:
    start = event.get("start", {})
    end = event.get("end", {})

    if "date" in start:
        start_date_value = date.fromisoformat(start["date"])
        end_date_value = (
            date.fromisoformat(end["date"]) - timedelta(days=1)
            if "date" in end
            else start_date_value
        )
    elif "dateTime" in start:
        start_date_value = datetime.fromisoformat(start["dateTime"]).astimezone(TZ).date()
        end_date_value = (
            datetime.fromisoformat(end["dateTime"]).astimezone(TZ).date()
            if "dateTime" in end
            else start_date_value
        )
    else:
        return []

    days: list[date] = []
    current = start_date_value
    while current <= end_date_value:
        days.append(current)
        current += timedelta(days=1)
    return days
