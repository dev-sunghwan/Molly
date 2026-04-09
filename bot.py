"""
bot.py — Entry point. Telegram polling loop (python-telegram-bot v20, async).

Flow per message:
  1. Check sender is in ALLOWED_USER_IDS → reject if not
  2. Parse message text via commands.parse()
  3. Dispatch to calendar_client or return error/usage
  4. Send reply
"""
import logging
import sys
from datetime import timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

import calendar_client
import commands
import config
import scheduler as sched_module
import utils

# ── Logging ───────────────────────────────────────────────────────────────────
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

# Google Calendar service — initialised in main() before polling starts
gcal_service = None


# ── /help handler ────────────────────────────────────────────────────────────

async def help_command(update: Update, context) -> None:
    user = update.effective_user
    if user.id not in config.ALLOWED_USER_IDS:
        return
    await update.message.reply_text(commands.USAGE)


# ── Message handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, context) -> None:
    user = update.effective_user

    # ── Whitelist check ───────────────────────────────────────────────────────
    if user.id not in config.ALLOWED_USER_IDS:
        log.warning("Rejected message from unauthorised user id=%s name=%s", user.id, user.full_name)
        return  # Silent reject

    text = (update.message.text or "").strip()
    if not text:
        return

    log.info("Message from %s (id=%s): %s", user.full_name, user.id, text)

    # ── Parse command ─────────────────────────────────────────────────────────
    cmd = commands.parse(text)

    if "error" in cmd:
        await update.message.reply_text(cmd["error"])
        return

    # ── Dispatch ──────────────────────────────────────────────────────────────
    try:
        if cmd["cmd"] == "today":
            target = utils._today_local()
            events = calendar_client.list_events(gcal_service, target)
            reply = utils.format_event_list(events, target)
            await update.message.reply_text(reply)

        elif cmd["cmd"] == "tomorrow":
            target = utils._today_local() + timedelta(days=1)
            events = calendar_client.list_events(gcal_service, target)
            reply = utils.format_event_list(events, target)
            await update.message.reply_text(reply)

        elif cmd["cmd"] == "week":
            monday, sunday = utils.get_week_range()
            events = calendar_client.list_events_range(gcal_service, monday, sunday)
            reply = utils.format_week(events, monday, sunday)
            await update.message.reply_text(reply)

        elif cmd["cmd"] == "date":
            target = cmd["date"]
            events = calendar_client.list_events(gcal_service, target)
            reply = utils.format_event_list(events, target)
            await update.message.reply_text(reply)

        elif cmd["cmd"] == "add":
            reply = calendar_client.add_event(gcal_service, cmd)
            await update.message.reply_text(reply)

        elif cmd["cmd"] == "delete":
            reply = calendar_client.find_and_delete_event(
                gcal_service, cmd["calendar"], cmd["date"], cmd["title"]
            )
            await update.message.reply_text(reply)

        elif cmd["cmd"] == "edit":
            reply = calendar_client.find_and_edit_event(
                gcal_service, cmd["calendar"], cmd["date"], cmd["title"], cmd["changes"]
            )
            await update.message.reply_text(reply)

    except Exception as e:
        log.exception("Unhandled error while processing command: %s", cmd)
        await update.message.reply_text(
            f"Something went wrong. Please try again.\n({type(e).__name__})"
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("Molly starting up...")

    # Validate config before doing anything else
    config.validate()

    # Authenticate with Google Calendar once at startup
    global gcal_service
    log.info("Authenticating with Google Calendar...")
    gcal_service = calendar_client.authenticate()
    log.info("Google Calendar authentication successful.")

    # Build and start Telegram application
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start APScheduler (daily summary + per-event reminders)
    scheduler = sched_module.create_scheduler(gcal_service, app.bot)
    scheduler.start()
    log.info(
        "Scheduler started — daily summary at %s, reminders %d min before.",
        config.SCHEDULER_SUMMARY_TIME,
        config.SCHEDULER_REMINDER_MINUTES,
    )

    log.info("Molly is running. Waiting for Telegram messages...")
    app.run_polling()

    scheduler.shutdown(wait=False)
    log.info("Molly shutting down.")


if __name__ == "__main__":
    main()
