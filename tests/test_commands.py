"""
tests/test_commands.py — Unit tests for command parsing in commands.py.
Run with: python -m pytest tests/ -v
      or: python tests/test_commands.py
"""
import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

import commands
import utils

def today() -> date:
    return utils._today_local()

def tomorrow() -> date:
    return today() + timedelta(days=1)


# ── today / tomorrow ──────────────────────────────────────────────────────────

def test_today():
    assert commands.parse("today") == {"cmd": "today"}
    assert commands.parse("Today") == {"cmd": "today"}
    assert commands.parse("  today  ") == {"cmd": "today"}

def test_tomorrow():
    assert commands.parse("tomorrow") == {"cmd": "tomorrow"}
    assert commands.parse("TOMORROW") == {"cmd": "tomorrow"}


# ── add — happy path ──────────────────────────────────────────────────────────

def test_add_basic():
    result = commands.parse("add YounHa tennis tomorrow 17:00-18:00")
    assert result["cmd"] == "add"
    assert result["calendar"] == "younha"
    assert result["title"] == "tennis"
    assert result["date"] == tomorrow()
    assert result["start"] == "17:00"
    assert result["end"] == "18:00"

def test_add_multiword_title():
    result = commands.parse("add Family Sunday roast tomorrow 13:00-15:00")
    assert result["cmd"] == "add"
    assert result["title"] == "Sunday roast"

def test_add_ddmmyyyy_date():
    result = commands.parse("add SungHwan meeting 15-04-2026 09:00-10:00")
    assert result["cmd"] == "add"
    assert result["date"] == date(2026, 4, 15)

def test_add_day_name():
    result = commands.parse("add HaNeul swimming Sat 08:00-09:00")
    assert result["cmd"] == "add"
    assert result["date"] is not None
    delta = (result["date"] - today()).days
    assert 0 <= delta <= 6

def test_add_single_time():
    result = commands.parse("add SungHwan dentist tomorrow 10:00")
    assert result["cmd"] == "add"
    assert result["start"] == "10:00"
    assert result["end"] == "11:00"

def test_add_case_insensitive_calendar():
    result = commands.parse("add FAMILY dinner tomorrow 19:00-21:00")
    assert result["cmd"] == "add"
    assert result["calendar"] == "family"


# ── add — error cases ─────────────────────────────────────────────────────────

def test_add_unknown_calendar():
    result = commands.parse("add NotAName tennis tomorrow 17:00-18:00")
    assert "error" in result
    assert "Unknown calendar" in result["error"]

def test_add_missing_tokens():
    # Only cal + time (no title) → error
    result = commands.parse("add YounHa 14:00")
    assert "error" in result

def test_add_no_date_defaults_today():
    # add <cal> <title> <time> — no date → defaults to today
    result = commands.parse("add SungHwan dentist 14:00")
    assert result["cmd"] == "add"
    assert result["title"] == "dentist"
    assert result["date"] == today()
    assert result["start"] == "14:00"

def test_add_bad_date_becomes_title():
    # "baddate" is not a valid date, so it becomes part of the title and date defaults to today
    result = commands.parse("add SungHwan meeting baddate 10:00-11:00")
    assert result["cmd"] == "add"
    assert result["title"] == "meeting baddate"
    assert result["date"] == today()

def test_add_bad_time():
    result = commands.parse("add SungHwan meeting tomorrow badtime")
    assert "error" in result
    assert "time" in result["error"].lower()


# ── week ─────────────────────────────────────────────────────────────────────

def test_week():
    assert commands.parse("week") == {"cmd": "week"}
    assert commands.parse("WEEK") == {"cmd": "week"}


# ── date-only query ───────────────────────────────────────────────────────────

def test_date_query_ddmmyyyy():
    result = commands.parse("09-04-2026")
    assert result["cmd"] == "date"
    assert result["date"] == date(2026, 4, 9)

def test_date_query_day_name():
    result = commands.parse("Fri")
    assert result["cmd"] == "date"
    delta = (result["date"] - today()).days
    assert 0 <= delta <= 6


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_basic():
    result = commands.parse("delete SungHwan today dentist")
    assert result["cmd"] == "delete"
    assert result["calendar"] == "sunghwan"
    assert result["date"] == today()
    assert result["title"] == "dentist"

def test_delete_multiword_title():
    result = commands.parse("delete YounHa tomorrow Sunday roast")
    assert result["cmd"] == "delete"
    assert result["title"] == "Sunday roast"

def test_delete_unknown_calendar():
    result = commands.parse("delete NoName today event")
    assert "error" in result

def test_delete_bad_date():
    # "baddate" is not a recognised date, so it becomes part of the title
    # and the search spans the next 90 days (no error)
    result = commands.parse("delete SungHwan baddate event")
    assert result["cmd"] == "delete"
    assert result["date"] is None
    assert result["title"] == "baddate event"

def test_delete_missing_tokens():
    result = commands.parse("delete SungHwan today")  # no title
    assert "error" in result


# ── all-day events ────────────────────────────────────────────────────────────

def test_add_all_day_with_date():
    result = commands.parse("add Family BBQ Sat")
    assert result["cmd"] == "add"
    assert result.get("all_day") is True
    assert result.get("start") is None
    assert result["title"] == "BBQ"
    delta = (result["date"] - today()).days
    assert 0 <= delta <= 6  # next Saturday

def test_add_all_day_today_implicit():
    result = commands.parse("add SungHwan holiday")
    assert result["cmd"] == "add"
    assert result.get("all_day") is True
    assert result["date"] == today()
    assert result["title"] == "holiday"

def test_add_all_day_explicit_date():
    result = commands.parse("add Family BBQ 25-12-2026")
    assert result["cmd"] == "add"
    assert result.get("all_day") is True
    assert result["date"] == date(2026, 12, 25)
    assert result["title"] == "BBQ"


# ── recurring events ──────────────────────────────────────────────────────────

def test_add_recurring_timed():
    result = commands.parse("add YounHa tennis every Mon 17:00-18:00")
    assert result["cmd"] == "add"
    assert result["title"] == "tennis"
    assert result["start"] == "17:00"
    assert result["end"] == "18:00"
    assert result["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=MO"]
    assert result["date"].weekday() == 0  # Monday

def test_add_recurring_all_day():
    result = commands.parse("add HaNeul swimming every Wed")
    assert result["cmd"] == "add"
    assert result.get("all_day") is True
    assert result["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=WE"]
    assert result["date"].weekday() == 2  # Wednesday

def test_add_recurring_multiword_title():
    result = commands.parse("add Family Sunday roast every Sun 13:00-15:00")
    assert result["cmd"] == "add"
    assert result["title"] == "Sunday roast"
    assert result["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=SU"]

def test_add_recurring_bad_day():
    result = commands.parse("add YounHa tennis every Xyz 17:00")
    assert "error" in result

def test_add_recurring_no_title():
    result = commands.parse("add YounHa every Mon 17:00")
    assert "error" in result
    assert "title" in result["error"].lower()


# ── edit ─────────────────────────────────────────────────────────────────────

def test_edit_time_with_date():
    # date provided → narrow search to that day
    result = commands.parse("edit SungHwan today dentist time 15:00-16:00")
    assert result["cmd"] == "edit"
    assert result["calendar"] == "sunghwan"
    assert result["date"] == today()
    assert result["title"] == "dentist"
    assert result["changes"] == {"start": "15:00", "end": "16:00"}

def test_edit_time_without_date():
    # no date → search upcoming events
    result = commands.parse("edit SungHwan dentist time 15:00-16:00")
    assert result["cmd"] == "edit"
    assert result["date"] is None
    assert result["title"] == "dentist"
    assert result["changes"] == {"start": "15:00", "end": "16:00"}

def test_edit_date_field():
    result = commands.parse("edit YounHa tennis date Sat")
    assert result["cmd"] == "edit"
    assert result["title"] == "tennis"
    assert result["date"] is None  # no search-date given
    assert result["changes"]["date"].weekday() == 5  # Saturday

def test_edit_title_field():
    result = commands.parse("edit SungHwan dentist title check-up")
    assert result["cmd"] == "edit"
    assert result["title"] == "dentist"
    assert result["changes"] == {"title": "check-up"}

def test_edit_multiword_title():
    result = commands.parse("edit Family Sunday roast title Sunday BBQ")
    assert result["cmd"] == "edit"
    assert result["title"] == "Sunday roast"
    assert result["changes"] == {"title": "Sunday BBQ"}

def test_edit_multiword_title_with_date():
    result = commands.parse("edit Family today Sunday roast title Sunday BBQ")
    assert result["cmd"] == "edit"
    assert result["date"] == today()
    assert result["title"] == "Sunday roast"
    assert result["changes"] == {"title": "Sunday BBQ"}

def test_edit_unknown_calendar():
    result = commands.parse("edit NoName event time 10:00")
    assert "error" in result

def test_edit_missing_field():
    result = commands.parse("edit SungHwan dentist")
    assert "error" in result

def test_edit_single_time():
    result = commands.parse("edit SungHwan dentist time 15:00")
    assert result["cmd"] == "edit"
    assert result["changes"]["start"] == "15:00"
    assert result["changes"]["end"] == "16:00"


# ── week next / month ─────────────────────────────────────────────────────────

def test_week_next():
    assert commands.parse("week next") == {"cmd": "week_next"}
    assert commands.parse("WEEK NEXT") == {"cmd": "week_next"}

def test_month():
    assert commands.parse("month") == {"cmd": "month"}
    assert commands.parse("MONTH") == {"cmd": "month"}

def test_month_next():
    assert commands.parse("month next") == {"cmd": "month_next"}


# ── search ────────────────────────────────────────────────────────────────────

def test_search_basic():
    result = commands.parse("search tennis")
    assert result == {"cmd": "search", "keyword": "tennis"}

def test_search_multiword():
    result = commands.parse("search Sunday roast")
    assert result == {"cmd": "search", "keyword": "Sunday roast"}

def test_search_empty():
    result = commands.parse("search")
    # "search" alone without a space + keyword falls through to unrecognised
    assert "error" in result

def test_search_empty_keyword():
    result = commands.parse("search ")
    assert "error" in result


# ── next ──────────────────────────────────────────────────────────────────────

def test_next_all():
    result = commands.parse("next")
    assert result == {"cmd": "next", "calendar": None}

def test_next_calendar():
    result = commands.parse("next YounHa")
    assert result["cmd"] == "next"
    assert result["calendar"] == "younha"

def test_next_unknown_calendar():
    result = commands.parse("next NoName")
    assert "error" in result


# ── delete without date ───────────────────────────────────────────────────────

def test_delete_no_date():
    result = commands.parse("delete SungHwan dentist")
    assert result["cmd"] == "delete"
    assert result["calendar"] == "sunghwan"
    assert result["date"] is None
    assert result["title"] == "dentist"

def test_delete_no_date_multiword():
    result = commands.parse("delete YounHa Sunday roast")
    assert result["cmd"] == "delete"
    assert result["date"] is None
    assert result["title"] == "Sunday roast"

def test_delete_with_date_still_works():
    result = commands.parse("delete SungHwan today dentist")
    assert result["cmd"] == "delete"
    assert result["date"] == today()
    assert result["title"] == "dentist"


# ── upcoming ─────────────────────────────────────────────────────────────────

def test_upcoming_all():
    result = commands.parse("upcoming")
    assert result == {"cmd": "upcoming", "calendar": None, "limit": 10}

def test_upcoming_calendar():
    result = commands.parse("upcoming YounHa")
    assert result["cmd"] == "upcoming"
    assert result["calendar"] == "younha"
    assert result["limit"] == 10

def test_upcoming_calendar_with_limit():
    result = commands.parse("upcoming YounHa 20")
    assert result["cmd"] == "upcoming"
    assert result["calendar"] == "younha"
    assert result["limit"] == 20

def test_upcoming_limit_capped():
    result = commands.parse("upcoming YounHa 999")
    assert result["limit"] == 50

def test_upcoming_all_with_limit():
    result = commands.parse("upcoming 15")
    assert result["cmd"] == "upcoming"
    assert result["calendar"] is None
    assert result["limit"] == 15

def test_upcoming_unknown_calendar():
    result = commands.parse("upcoming NoName")
    assert "error" in result

def test_upcoming_bad_limit():
    result = commands.parse("upcoming YounHa notanumber")
    assert "error" in result


# ── unrecognised input ────────────────────────────────────────────────────────

def test_unknown_command():
    result = commands.parse("hello Molly")
    assert "error" in result

def test_empty_string():
    result = commands.parse("")
    assert "error" in result


# ── Self-running ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_today, test_tomorrow,
        test_add_basic, test_add_multiword_title, test_add_ddmmyyyy_date,
        test_add_day_name, test_add_single_time, test_add_case_insensitive_calendar,
        test_add_unknown_calendar, test_add_missing_tokens,
        test_add_no_date_defaults_today, test_add_bad_date_becomes_title, test_add_bad_time,
        test_week,
        test_date_query_ddmmyyyy, test_date_query_day_name,
        test_delete_basic, test_delete_multiword_title, test_delete_unknown_calendar,
        test_delete_bad_date, test_delete_missing_tokens,
        test_add_all_day_with_date, test_add_all_day_today_implicit, test_add_all_day_explicit_date,
        test_add_recurring_timed, test_add_recurring_all_day, test_add_recurring_multiword_title,
        test_add_recurring_bad_day, test_add_recurring_no_title,
        test_edit_time_with_date, test_edit_time_without_date,
        test_edit_date_field, test_edit_title_field,
        test_edit_multiword_title, test_edit_multiword_title_with_date,
        test_edit_unknown_calendar, test_edit_missing_field, test_edit_single_time,
        test_week_next, test_month, test_month_next,
        test_search_basic, test_search_multiword, test_search_empty, test_search_empty_keyword,
        test_next_all, test_next_calendar, test_next_unknown_calendar,
        test_delete_no_date, test_delete_no_date_multiword, test_delete_with_date_still_works,
        test_upcoming_all, test_upcoming_calendar, test_upcoming_calendar_with_limit,
        test_upcoming_limit_capped, test_upcoming_all_with_limit,
        test_upcoming_unknown_calendar, test_upcoming_bad_limit,
        test_unknown_command, test_empty_string,
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
