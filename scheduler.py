"""
scheduler.py — APScheduler jobs for Molly.

Jobs:
  1. daily_summary    — Every day at configured time, send today's events to all users.
  2. check_reminders  — Every 5 minutes, check upcoming events and send reminders.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from calendar_repository import CalendarRepository
import config
import utils

log = logging.getLogger(__name__)

# File-backed set of "event_id|start_iso" strings already reminded.
# Persists across restarts. Entries older than today are pruned on load.
_REMINDED_PATH: Path = config.ROOT / "data" / "reminded.json"


def _load_reminded() -> set[str]:
    """Load the reminded set from disk, pruning entries from past days."""
    if not _REMINDED_PATH.exists():
        return set()
    try:
        data: list[str] = json.loads(_REMINDED_PATH.read_text(encoding="utf-8"))
        today_iso = utils._today_local().isoformat()
        # Keep only entries whose embedded date is today or in the future
        return {k for k in data if k.split("|")[-1][:10] >= today_iso}
    except Exception:
        return set()


def _save_reminded(reminded: set[str]) -> None:
    """Persist the reminded set to disk."""
    try:
        _REMINDED_PATH.parent.mkdir(parents=True, exist_ok=True)
        _REMINDED_PATH.write_text(json.dumps(sorted(reminded)), encoding="utf-8")
    except Exception as e:
        log.warning("[Scheduler] Could not save reminded set: %s", e)


_reminded: set[str] = _load_reminded()

# Tracks the previous check time to define the reminder window.
# None on first run — defaults to (now - 5min) when first check fires.
_last_check: datetime | None = None


def _cal_key_for_event(event: dict) -> str:
    """Return the lowercase calendar key for an event dict."""
    display = event.get("_calendar_name", "").lower()
    return next(
        (k for k, v in config.CALENDAR_DISPLAY_NAMES.items() if v.lower() == display),
        display,
    )


def create_scheduler(calendar_repo: CalendarRepository, bot) -> AsyncIOScheduler:
    """
    Build and return an AsyncIOScheduler with all jobs registered.
    Call scheduler.start() after this.

    Parameters
    ----------
    calendar_repo : backend-agnostic calendar repository
    bot          : telegram.Bot instance (app.bot from the Application object)
    """
    tz = utils.TZ
    scheduler = AsyncIOScheduler(timezone=tz)

    hour, minute = map(int, config.SCHEDULER_SUMMARY_TIME.split(":"))
    t_hour, t_minute = map(int, config.SCHEDULER_TOMORROW_SUMMARY_TIME.split(":"))

    scheduler.add_job(
        _daily_summary,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
        args=[calendar_repo, bot],
        id="daily_summary",
        name="Daily morning summary",
        misfire_grace_time=300,
    )

    scheduler.add_job(
        _tomorrow_summary,
        trigger=CronTrigger(hour=t_hour, minute=t_minute, timezone=tz),
        args=[calendar_repo, bot],
        id="tomorrow_summary",
        name="Tomorrow evening preview",
        misfire_grace_time=300,
    )

    scheduler.add_job(
        _check_reminders,
        trigger=CronTrigger(minute="*/5", timezone=tz),
        args=[calendar_repo, bot],
        id="check_reminders",
        name="Per-event reminder check",
        misfire_grace_time=60,
    )

    return scheduler


async def _daily_summary(calendar_repo: CalendarRepository, bot) -> None:
    """Send today's event summary to each user, filtered to their subscribed calendars."""
    today = utils._today_local()
    log.info("[Scheduler] Sending daily summary for %s", today)

    try:
        all_events = calendar_repo.list_events(today)
    except Exception:
        log.exception("[Scheduler] Failed to fetch events for daily summary")
        error_text = "Could not fetch today's events."
        for user_id in config.ALLOWED_USER_IDS:
            try:
                await bot.send_message(chat_id=user_id, text=error_text, parse_mode="HTML")
            except Exception as e:
                log.warning("[Scheduler] Could not send error to user_id=%s: %s", user_id, e)
        return

    for user_id, udata in config.USERS.items():
        subscribed = set(udata["reminder_calendars"])
        user_events = [
            ev for ev in all_events
            if _cal_key_for_event(ev) in subscribed
        ]
        text = utils.format_event_list(user_events, today)
        try:
            await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
        except Exception as e:
            log.warning("[Scheduler] Could not send daily summary to user_id=%s: %s", user_id, e)


async def _tomorrow_summary(calendar_repo: CalendarRepository, bot) -> None:
    """Send tomorrow's event preview to each user, filtered to their subscribed calendars."""
    from datetime import timedelta
    tomorrow = utils._today_local() + timedelta(days=1)
    log.info("[Scheduler] Sending tomorrow summary for %s", tomorrow)

    try:
        all_events = calendar_repo.list_events(tomorrow)
    except Exception:
        log.exception("[Scheduler] Failed to fetch events for tomorrow summary")
        return

    for user_id, udata in config.USERS.items():
        subscribed = set(udata["reminder_calendars"])
        user_events = [
            ev for ev in all_events
            if _cal_key_for_event(ev) in subscribed
        ]
        text = utils.format_event_list(user_events, tomorrow)
        # Prefix to distinguish from the morning summary
        text = "Tomorrow:\n" + text
        try:
            await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
        except Exception as e:
            log.warning("[Scheduler] Could not send tomorrow summary to user_id=%s: %s", user_id, e)


async def _check_reminders(calendar_repo: CalendarRepository, bot) -> None:
    """
    Send reminders for events whose reminder_time (= start - reminder_delta)
    falls in the window (prev_check, now].

    Using a sliding window instead of a fixed lookahead means the reminder
    fires within one check interval (~5 min) of the exact target time,
    regardless of when the bot was started.

    CronTrigger(minute='*/5') keeps checks clock-aligned (:00, :05, :10 ...)
    so on-the-hour events get reminded at exactly the right time.
    """
    global _last_check

    tz = utils.TZ
    now = datetime.now(tz)
    reminder_delta = timedelta(minutes=config.SCHEDULER_REMINDER_MINUTES)
    check_interval = timedelta(minutes=5)

    # On first run after (re)start, look back one interval to avoid missing
    # events whose reminder_time passed just before the bot came up.
    prev = _last_check if _last_check is not None else (now - check_interval)
    _last_check = now

    # Fetch events in the window where their start time could be relevant:
    # from (prev + reminder_delta) to (now + reminder_delta + buffer)
    search_start = (prev + reminder_delta).date()
    search_end   = (now  + reminder_delta + check_interval).date()

    try:
        events = calendar_repo.list_events_range(search_start, search_end)
    except Exception:
        log.exception("[Scheduler] Failed to fetch events for reminder check")
        return

    for event in events:
        start = event.get("start", {})

        # Skip all-day events — no meaningful start time for a reminder
        if "dateTime" not in start:
            continue

        event_id = event.get("id", "")
        start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
        reminder_time = start_dt - reminder_delta

        # Fire if the reminder_time falls in (prev, now]
        if prev < reminder_time <= now:
            occurrence_key = f"{event_id}|{start_dt.isoformat()}"

            if occurrence_key not in _reminded:
                _reminded.add(occurrence_key)
                _save_reminded(_reminded)
                minutes_away = round((start_dt - now).total_seconds() / 60)
                cal_label = event.get("_calendar_name", "")
                label = f"[{cal_label}] " if cal_label else ""
                text = (
                    f"Reminder — in {minutes_away} min:\n"
                    f"  {label}{utils.event_display_summary(event)}\n"
                    f"  {start_dt.strftime('%H:%M')}"
                )
                log.info(
                    "[Scheduler] Sending reminder for '%s' at %s",
                    event.get("summary"), start_dt.strftime("%H:%M"),
                )
                event_cal_key = _cal_key_for_event(event)
                for user_id, udata in config.USERS.items():
                    if event_cal_key not in udata["reminder_calendars"]:
                        continue
                    try:
                        await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
                    except Exception as e:
                        log.warning(
                            "[Scheduler] Could not send reminder to user_id=%s: %s",
                            user_id, e,
                        )
