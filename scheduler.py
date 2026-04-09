"""
scheduler.py — APScheduler jobs for Molly.

Jobs:
  1. daily_summary    — Every day at configured time, send today's events to all users.
  2. check_reminders  — Every 5 minutes, check upcoming events and send reminders.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import calendar_client
import config
import utils

log = logging.getLogger(__name__)

# In-memory set of (event_id, date_iso) already reminded.
# Resets on restart — acceptable for Phase 2.
_reminded: set[tuple[str, str]] = set()


def create_scheduler(gcal_service, bot) -> AsyncIOScheduler:
    """
    Build and return an AsyncIOScheduler with all jobs registered.
    Call scheduler.start() after this.

    Parameters
    ----------
    gcal_service : Google Calendar API service object
    bot          : telegram.Bot instance (app.bot from the Application object)
    """
    tz = utils.TZ
    scheduler = AsyncIOScheduler(timezone=tz)

    hour, minute = map(int, config.SCHEDULER_SUMMARY_TIME.split(":"))

    scheduler.add_job(
        _daily_summary,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
        args=[gcal_service, bot],
        id="daily_summary",
        name="Daily morning summary",
        misfire_grace_time=300,  # fire up to 5 min late if bot was briefly down
    )

    scheduler.add_job(
        _check_reminders,
        trigger=IntervalTrigger(minutes=5),
        args=[gcal_service, bot],
        id="check_reminders",
        name="Per-event reminder check",
        misfire_grace_time=60,
    )

    return scheduler


async def _daily_summary(gcal_service, bot) -> None:
    """Send today's event summary to all allowed users."""
    today = utils._today_local()
    log.info("[Scheduler] Sending daily summary for %s", today)
    try:
        events = calendar_client.list_events(gcal_service, today)
        text = utils.format_event_list(events, today)
    except Exception as e:
        log.exception("[Scheduler] Failed to fetch events for daily summary")
        text = f"Could not fetch today's events. ({type(e).__name__})"

    for user_id in config.ALLOWED_USER_IDS:
        try:
            await bot.send_message(chat_id=user_id, text=text)
        except Exception as e:
            log.warning(
                "[Scheduler] Could not send daily summary to user_id=%s: %s", user_id, e
            )


async def _check_reminders(gcal_service, bot) -> None:
    """
    Check for events starting within the reminder window and send reminders.
    - Only timed events are reminded (all-day events are skipped).
    - Uses an in-memory set to avoid duplicate reminders within the same run.
    """
    tz = utils.TZ
    now = datetime.now(tz)
    reminder_delta = timedelta(minutes=config.SCHEDULER_REMINDER_MINUTES)
    target_time = now + reminder_delta

    today = now.date()
    tomorrow = today + timedelta(days=1)

    try:
        # Fetch today + tomorrow to handle reminders that cross midnight
        events = calendar_client.list_events_range(gcal_service, today, tomorrow)
    except Exception as e:
        log.exception("[Scheduler] Failed to fetch events for reminder check")
        return

    for event in events:
        start = event.get("start", {})

        # Skip all-day events — no meaningful start time for a reminder
        if "dateTime" not in start:
            continue

        event_id = event.get("id", "")
        start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)

        # Fire if the event starts within (now, now + reminder_window]
        if now < start_dt <= target_time:
            occurrence_key = (event_id, start_dt.date().isoformat())

            if occurrence_key not in _reminded:
                _reminded.add(occurrence_key)
                minutes_away = int((start_dt - now).total_seconds() / 60)
                cal_label = event.get("_calendar_name", "")
                label = f"[{cal_label}] " if cal_label else ""
                text = (
                    f"Reminder — in {minutes_away} min:\n"
                    f"  {label}{event.get('summary', '(no title)')}\n"
                    f"  {start_dt.strftime('%H:%M')}"
                )
                log.info(
                    "[Scheduler] Sending reminder for '%s' at %s",
                    event.get("summary"), start_dt.strftime("%H:%M"),
                )
                for user_id in config.ALLOWED_USER_IDS:
                    try:
                        await bot.send_message(chat_id=user_id, text=text)
                    except Exception as e:
                        log.warning(
                            "[Scheduler] Could not send reminder to user_id=%s: %s",
                            user_id, e,
                        )
