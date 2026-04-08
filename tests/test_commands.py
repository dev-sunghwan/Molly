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
    result = commands.parse("add YounHa tomorrow 17:00-18:00")  # no title
    # 3 tokens after "add" — title would be empty or date/time overlap ambiguously
    # parser sees: cal=YounHa, time=17:00-18:00, date=tomorrow, title=[]
    assert "error" in result

def test_add_bad_date():
    result = commands.parse("add SungHwan meeting baddate 10:00-11:00")
    assert "error" in result
    assert "date" in result["error"].lower()

def test_add_bad_time():
    result = commands.parse("add SungHwan meeting tomorrow badtime")
    assert "error" in result
    assert "time" in result["error"].lower()


# ── unrecognised input ────────────────────────────────────────────────────────

def test_unknown_command():
    result = commands.parse("hello Dobby")
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
        test_add_bad_date, test_add_bad_time,
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
