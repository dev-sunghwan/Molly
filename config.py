"""
config.py — Load and expose all app settings.
Reads from .env (secrets) and config.json (preferences).
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

# Locate project root (the directory this file lives in)
ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
CALENDAR_BACKEND: str = os.getenv("MOLLY_CALENDAR_BACKEND", "local").strip().lower()

# ── Load config.json ──────────────────────────────────────────────────────────
_config_path = ROOT / "config.json"
with _config_path.open(encoding="utf-8") as _f:
    _cfg = json.load(_f)

TIMEZONE: str = _cfg["timezone"]  # e.g. "Europe/London"

# Mapping: lowercase name → Google Calendar ID
# Keys are always stored/compared in lowercase.
CALENDARS: dict[str, str] = {k.lower(): v for k, v in _cfg["calendars"].items()}

# Mapping: lowercase name → display name (original casing from config.json)
CALENDAR_DISPLAY_NAMES: dict[str, str] = {k.lower(): k for k in _cfg["calendars"].keys()}

# Per-user settings: { user_id (int) → { "name": str, "reminder_calendars": [str] } }
# reminder_calendars stores lowercase keys matching CALENDARS.
_users_raw: dict = _cfg.get("users", {})
USERS: dict[int, dict] = {
    int(uid): {
        "name": udata["name"],
        "reminder_calendars": [c.lower() for c in udata.get("reminder_calendars", [])],
    }
    for uid, udata in _users_raw.items()
}

# Set of Telegram user IDs that are allowed to use the bot
# Derived from users block; falls back to legacy allowed_user_ids if users is absent.
if USERS:
    ALLOWED_USER_IDS: set[int] = set(USERS.keys())
else:
    ALLOWED_USER_IDS: set[int] = set(_cfg.get("allowed_user_ids", []))

# Scheduler settings
_sched = _cfg.get("scheduler", {})
SCHEDULER_SUMMARY_TIME: str          = _sched.get("daily_summary_time", "08:00")
SCHEDULER_TOMORROW_SUMMARY_TIME: str = _sched.get("tomorrow_summary_time", "21:00")
SCHEDULER_REMINDER_MINUTES: int      = int(_sched.get("reminder_minutes_before", 60))

# ── Derived helpers ───────────────────────────────────────────────────────────
VALID_CALENDAR_NAMES: list[str] = list(_cfg["calendars"].keys())  # original casing

CREDENTIALS_PATH: Path = ROOT / "credentials.json"
TOKEN_PATH: Path = ROOT / "token.json"
GMAIL_CREDENTIALS_PATH: Path = ROOT / "credentials.json"
GMAIL_TOKEN_PATH: Path = ROOT / "gmail_token.json"
LOG_PATH: Path = ROOT / "molly.log"
STATE_DB_PATH: Path = ROOT / "data" / "molly_state.db"
LOCAL_CALENDAR_DB_PATH: Path = ROOT / "data" / "local_calendar.db"


def validate():
    """Raise a clear error if critical config is missing."""
    errors = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is not set in .env")
    if not ALLOWED_USER_IDS or 0 in ALLOWED_USER_IDS:
        errors.append("allowed_user_ids in config.json contains placeholder value 0 — set a real Telegram user ID")
    if CALENDAR_BACKEND == "google":
        if not CREDENTIALS_PATH.exists():
            errors.append(f"credentials.json not found at {CREDENTIALS_PATH}")
        for name, cal_id in CALENDARS.items():
            if cal_id.startswith("REPLACE_WITH"):
                errors.append(f"Calendar ID for '{name}' is still a placeholder in config.json")
    elif CALENDAR_BACKEND != "local":
        errors.append(f"Unsupported MOLLY_CALENDAR_BACKEND: '{CALENDAR_BACKEND}'")
    if errors:
        msg = "\n".join(f"  ❌ {e}" for e in errors)
        raise SystemExit(f"[Molly] Config errors found:\n{msg}\n\nEdit config.json and .env before running.")
