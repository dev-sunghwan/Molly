"""
bot.py — Entry point. Telegram polling loop (python-telegram-bot v20, async).

Flow per message:
  1. Check sender is in ALLOWED_USER_IDS → reject if not
  2. Parse message text via commands.parse()
  3. Dispatch to the calendar repository or return error/usage
  4. Send reply
"""
import logging
import sys

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from calendar_repository import CalendarRepository
import clarification_state
import commands
import config
from intent_adapter import parse_text_to_intent
from intent_models import ResolutionStatus
from molly_core import MollyCore
import scheduler as sched_module
import spouse_notifications
import state_store
import telegram_extractor_provider
import telegram_nlu

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

# Calendar repository — initialised in main() before polling starts
calendar_repo = None
core = None


# ── /help handler ────────────────────────────────────────────────────────────

async def help_command(update: Update, context) -> None:
    user = update.effective_user
    if user.id not in config.ALLOWED_USER_IDS:
        return
    await update.message.reply_text(commands.USAGE, parse_mode="HTML")


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

    # ── Dispatch ──────────────────────────────────────────────────────────────
    try:
        pending_resolution = clarification_state.apply_reply(user.id, text)
        if pending_resolution is not None:
            if pending_resolution.status == ResolutionStatus.NEEDS_CLARIFICATION:
                clarification_state.set_pending(user.id, pending_resolution)
                prompt = pending_resolution.clarification_prompt or "Molly needs more information."
                await update.message.reply_text(prompt, parse_mode="HTML")
                return
            reply = core.execute_resolution(pending_resolution, user_id=user.id)
            await update.message.reply_text(reply, parse_mode="HTML")
            await spouse_notifications.notify_spouse_via_bot(
                context.application.bot,
                user.id,
                pending_resolution.intent,
                success=not reply.startswith("❌"),
            )
            return

        resolution = parse_text_to_intent(text, commands.parse)
        if resolution.status == ResolutionStatus.INVALID:
            extractor = context.application.bot_data.get("telegram_extractor")
            extracted_draft = telegram_extractor_provider.extract_draft(text, extractor)
            natural_language_resolution = telegram_nlu.parse_free_text_to_intent(
                text,
                extracted_draft=extracted_draft,
            )
            if natural_language_resolution is not None:
                resolution = natural_language_resolution

        if resolution.status == ResolutionStatus.INVALID:
            await update.message.reply_text(resolution.reason or commands.USAGE, parse_mode="HTML")
            return

        if resolution.status == ResolutionStatus.NEEDS_CLARIFICATION:
            clarification_state.set_pending(user.id, resolution)
            prompt = resolution.clarification_prompt or "Molly needs more information."
            await update.message.reply_text(prompt, parse_mode="HTML")
            return

        reply = core.execute_resolution(resolution, user_id=user.id)
        await update.message.reply_text(reply, parse_mode="HTML")
        await spouse_notifications.notify_spouse_via_bot(
            context.application.bot,
            user.id,
            resolution.intent,
            success=not reply.startswith("❌"),
        )

    except Exception as e:
        log.exception("Unhandled error while processing message text=%s", text)
        await update.message.reply_text(
            f"Something went wrong. Please try again.\n({type(e).__name__})",
            parse_mode="HTML",
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("Molly starting up...")

    # Validate config before doing anything else
    config.validate()
    state_store.init_db()

    # Authenticate with the configured calendar backend once at startup
    global calendar_repo, core
    log.info("Authenticating with calendar backend '%s'...", config.CALENDAR_BACKEND)
    calendar_repo = CalendarRepository.from_config()
    core = MollyCore(calendar_repo)
    log.info("Calendar backend authentication successful.")

    # Build and start Telegram application
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    extractor = telegram_extractor_provider.build_extractor_from_config()
    if extractor is not None:
        app.bot_data["telegram_extractor"] = extractor
        log.info(
            "Telegram extractor backend enabled: %s",
            config.TELEGRAM_EXTRACTOR_BACKEND,
        )
    else:
        log.info("Telegram extractor backend: heuristic fallback")
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start APScheduler (daily summary + per-event reminders)
    scheduler = sched_module.create_scheduler(calendar_repo, app.bot)
    scheduler.start()
    log.info(
        "Scheduler started — morning summary at %s, evening preview at %s, reminders %d min before.",
        config.SCHEDULER_SUMMARY_TIME,
        config.SCHEDULER_TOMORROW_SUMMARY_TIME,
        config.SCHEDULER_REMINDER_MINUTES,
    )

    log.info("Molly is running. Waiting for Telegram messages...")
    app.run_polling()

    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass  # event loop already closed on exit — harmless
    log.info("Molly shutting down.")


if __name__ == "__main__":
    main()
