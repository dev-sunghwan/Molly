"""
tests/test_utils.py — Unit tests for date/time parsing in utils.py.
Run with: python -m pytest tests/ -v
      or: python tests/test_utils.py
"""
import sys
from pathlib import Path
from datetime import date, timedelta

# Make sure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import utils

# ── Helpers ───────────────────────────────────────────────────────────────────

def today() -> date:
    return utils._today_local()

def tomorrow() -> date:
    return today() + timedelta(days=1)


# ── parse_date ────────────────────────────────────────────────────────────────

def test_today():
    assert utils.parse_date("today") == today()
    assert utils.parse_date("TODAY") == today()
    assert utils.parse_date("  today  ") == today()

def test_tomorrow():
    assert utils.parse_date("tomorrow") == tomorrow()
    assert utils.parse_date("Tomorrow") == tomorrow()

def test_ddmmyyyy():
    assert utils.parse_date("08-04-2026") == date(2026, 4, 8)
    assert utils.parse_date("01-01-2025") == date(2025, 1, 1)
    assert utils.parse_date("31-12-2099") == date(2099, 12, 31)

def test_ddmmyyyy_invalid():
    assert utils.parse_date("2026-04-08") is None  # Wrong order (YYYY-MM-DD)
    assert utils.parse_date("08/04/2026") is None  # Wrong separator
    assert utils.parse_date("notadate")   is None

def test_day_name_future():
    """A day name should resolve to within the next 7 days."""
    for day_str in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
        result = utils.parse_date(day_str)
        assert result is not None, f"parse_date('{day_str}') returned None"
        delta = (result - today()).days
        assert 0 <= delta <= 6, f"{day_str} resolved to {delta} days ahead"

def test_day_name_case_insensitive():
    assert utils.parse_date("Mon") == utils.parse_date("mon")
    assert utils.parse_date("FRI") == utils.parse_date("fri")


# ── parse_time ────────────────────────────────────────────────────────────────

def test_time_range():
    assert utils.parse_time("17:00-18:00") == ("17:00", "18:00")
    assert utils.parse_time("09:30-10:45") == ("09:30", "10:45")
    assert utils.parse_time("00:00-23:59") == ("00:00", "23:59")

def test_time_single_adds_one_hour():
    assert utils.parse_time("17:00") == ("17:00", "18:00")
    assert utils.parse_time("09:30") == ("09:30", "10:30")

def test_time_midnight_rollover():
    # 23:00 + 1h = 00:00
    assert utils.parse_time("23:00") == ("23:00", "00:00")

def test_time_invalid():
    assert utils.parse_time("25:00-26:00") is None  # Invalid hours
    assert utils.parse_time("notaTime")    is None
    assert utils.parse_time("")            is None


# ── format_date_header ────────────────────────────────────────────────────────

def test_format_date_header():
    d = date(2026, 4, 8)
    header = utils.format_date_header(d)
    assert "08-04" in header
    assert "2026" not in header
    assert "Wednesday" in header
    assert "📅" in header
    assert "<b>" not in header


def test_event_display_summary_prefers_current_summary_over_display_override():
    event = {
        "summary": "Cubs @ Green Lane Primary School",
        "_display_summary": "Cubs",
    }

    assert utils.event_display_summary(event) == "Cubs @ Green Lane Primary School"


def test_format_event_uses_korean_calendar_label():
    event = {
        "summary": "Alpha-Math",
        "_calendar_name": "YounHa",
        "start": {"dateTime": "2026-04-17T17:00:00+01:00"},
        "end": {"dateTime": "2026-04-17T18:00:00+01:00"},
    }

    line = utils.format_event(event)

    assert "[윤하]" in line
    assert "Alpha-Math" in line


def test_format_event_list_shows_calendar_label_per_line():
    d = date(2026, 4, 17)
    events = [
        {
            "summary": "swimming",
            "_calendar_name": "HaNeul",
            "start": {"dateTime": "2026-04-17T18:00:00+01:00"},
            "end": {"dateTime": "2026-04-17T18:30:00+01:00"},
        },
        {
            "summary": "Alpha-Math",
            "_calendar_name": "YounHa",
            "start": {"dateTime": "2026-04-17T17:00:00+01:00"},
            "end": {"dateTime": "2026-04-17T18:00:00+01:00"},
        },
    ]

    message = utils.format_event_list(events, d)

    assert "[하늘]" in message
    assert "[윤하]" in message
    assert "<b>HaNeul</b>" not in message
    assert "<b>YounHa</b>" not in message
    assert "<b>" not in message


# ── Self-running ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_today, test_tomorrow, test_ddmmyyyy, test_ddmmyyyy_invalid,
        test_day_name_future, test_day_name_case_insensitive,
        test_time_range, test_time_single_adds_one_hour,
        test_time_midnight_rollover, test_time_invalid, test_format_date_header,
        test_format_event_uses_korean_calendar_label,
        test_format_event_list_shows_calendar_label_per_line,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ❌  {t.__name__}  →  {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
