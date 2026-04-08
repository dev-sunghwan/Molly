"""
bot.py — Entry point. Telegram polling loop.

Flow per message:
  1. Check sender is in ALLOWED_USER_IDS → reject if not
  2. Parse message text via commands.parse()
  3. Dispatch to calendar_client or return error/usage
  4. Send reply
"""
import logging
import sys
from datetime import date

from telegram import Update
from telegram.ext import Filters, MessageHandler, Updater

import calendar_client
import commands
import config
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


# ── Message handler ───────────────────────────────────────────────────────────

def handle_message(update: Update, context) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id

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
        update.message.reply_text(cmd["error"])
        return

    # ── Dispatch ──────────────────────────────────────────────────────────────
    try:
        if cmd["cmd"] == "today":
            target = utils._today_local()
            events = calendar_client.list_events(gcal_service, target)
            reply = utils.format_event_list(events, target)
            update.message.reply_text(reply)

        elif cmd["cmd"] == "tomorrow":
            from datetime import timedelta
            target = utils._today_local() + timedelta(days=1)
            events = calendar_client.list_events(gcal_service, target)
            reply = utils.format_event_list(events, target)
            update.message.reply_text(reply)

        elif cmd["cmd"] == "add":
            reply = calendar_client.add_event(gcal_service, cmd)
            update.message.reply_text(reply)

    except Exception as e:
        log.exception("Unhandled error while processing command: %s", cmd)
        update.message.reply_text(f"⚠️ Something went wrong. Please try again.\n({type(e).__name__})")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("Dobby starting up...")

    # Validate config before doing anything else
    config.validate()

    # Authenticate with Google Calendar once at startup
    global gcal_service
    log.info("Authenticating with Google Calendar...")
    gcal_service = calendar_client.authenticate()
    log.info("Google Calendar authentication successful.")

    # Start Telegram bot
    updater = Updater(token=config.TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(
        MessageHandler(Filters.text & ~Filters.command, handle_message)
    )

    log.info("Dobby is running. Waiting for Telegram messages...")
    updater.start_polling()
    updater.idle()
    log.info("Dobby shutting down.")


if __name__ == "__main__":
    main()
