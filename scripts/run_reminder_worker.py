"""
Run Molly's scheduler jobs without the legacy Telegram polling bot.

This keeps reminders, daily summaries, and tomorrow previews alive in the
OpenClaw-centered architecture where Telegram conversation is handled elsewhere.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from telegram import Bot

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from calendar_repository import CalendarRepository
import config
import scheduler as sched_module
import state_store


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(config.LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


async def _run(startup_check: bool) -> None:
    config.validate()
    state_store.init_db()

    log.info("Reminder worker starting...")
    log.info("Authenticating with calendar backend '%s'...", config.CALENDAR_BACKEND)
    calendar_repo = CalendarRepository.from_config()
    log.info("Calendar backend authentication successful.")

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    scheduler = sched_module.create_scheduler(calendar_repo, bot)

    try:
        await bot.initialize()
        scheduler.start()
        log.info(
            "Reminder worker started — morning summary at %s, evening preview at %s, reminders %d min before.",
            config.SCHEDULER_SUMMARY_TIME,
            config.SCHEDULER_TOMORROW_SUMMARY_TIME,
            config.SCHEDULER_REMINDER_MINUTES,
        )

        if startup_check:
            log.info("Startup check complete. Shutting down without entering long-running mode.")
            return

        stop_event = asyncio.Event()
        _install_signal_handlers(stop_event)
        log.info("Reminder worker is running. Press Ctrl+C to stop.")
        await stop_event.wait()
    finally:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
        await bot.shutdown()
        log.info("Reminder worker stopped.")


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def _request_stop() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            # Fallback for platforms where asyncio signal handlers are unsupported.
            signal.signal(sig, lambda _signum, _frame: stop_event.set())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Molly reminders and summary jobs without the legacy bot runtime."
    )
    parser.add_argument(
        "--startup-check",
        action="store_true",
        help="Initialize the worker, start the scheduler, then exit immediately.",
    )
    args = parser.parse_args()

    asyncio.run(_run(startup_check=args.startup_check))


if __name__ == "__main__":
    main()
