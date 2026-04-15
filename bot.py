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
import clarification_state
import commands
import config
from intent_adapter import parse_text_to_intent
from intent_models import ExecutionResult, IntentAction, ResolutionStatus
import scheduler as sched_module
import state_store
import telegram_extractor_provider
import telegram_nlu
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

# Calendar backend service — initialised in main() before polling starts
gcal_service = None


# ── /help handler ────────────────────────────────────────────────────────────

async def help_command(update: Update, context) -> None:
    user = update.effective_user
    if user.id not in config.ALLOWED_USER_IDS:
        return
    await update.message.reply_text(commands.USAGE, parse_mode="HTML")


def _help_reply(topic: str | None) -> str:
    """Return the appropriate help string for a given topic."""
    if topic is None:
        return commands.USAGE
    topic = topic.strip().lower()
    mapping = {
        "view":      commands.HELP_VIEW,
        "add":       commands.HELP_ADD,
        "edit":      commands.HELP_EDIT,
        "delete":    commands.HELP_DELETE,
        "search":    commands.HELP_SEARCH,
        "calendars": commands.HELP_CALENDARS,
    }
    if topic in mapping:
        return mapping[topic]
    return f"No help available for '{topic}'.\n\nTopics: view · add · edit · delete · search · calendars"


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
            reply = _execute_resolution(pending_resolution)
            await update.message.reply_text(reply, parse_mode="HTML")
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

        reply = _execute_resolution(resolution)
        await update.message.reply_text(reply, parse_mode="HTML")

    except Exception as e:
        log.exception("Unhandled error while processing message text=%s", text)
        await update.message.reply_text(
            f"Something went wrong. Please try again.\n({type(e).__name__})",
            parse_mode="HTML",
        )


def _execute_resolution(resolution) -> str:
    """Execute a READY intent resolution with deterministic calendar logic."""
    intent = resolution.intent
    cmd_name = intent.metadata.get("command")

    if intent.action == IntentAction.VIEW_DAILY:
        if cmd_name == "tomorrow":
            target = utils._today_local() + timedelta(days=1)
        elif cmd_name == "date":
            target = intent.target_date
        else:
            target = utils._today_local()
        events = calendar_client.list_events(gcal_service, target)
        message = utils.format_event_list(events, target)
        _record_result(intent, message)
        return message

    if intent.action == IntentAction.VIEW_RANGE:
        if cmd_name == "week":
            monday, sunday = utils.get_week_range()
            events = calendar_client.list_events_range(gcal_service, monday, sunday)
            message = utils.format_week(events, monday, sunday)
            _record_result(intent, message)
            return message
        if cmd_name == "week_next":
            monday, sunday = utils.get_next_week_range()
            events = calendar_client.list_events_range(gcal_service, monday, sunday)
            message = utils.format_week(events, monday, sunday)
            _record_result(intent, message)
            return message
        if cmd_name == "month":
            first, last = utils.get_month_range(offset=0)
            events = calendar_client.list_events_range(gcal_service, first, last)
            message = utils.format_month(events, first, last)
            _record_result(intent, message)
            return message
        if cmd_name == "month_next":
            first, last = utils.get_month_range(offset=1)
            events = calendar_client.list_events_range(gcal_service, first, last)
            message = utils.format_month(events, first, last)
            _record_result(intent, message)
            return message
        if cmd_name == "next":
            events = calendar_client.get_next_events(gcal_service, intent.target_calendar, limit=1)
            message = calendar_client.format_next_events(events, intent.target_calendar)
            _record_result(intent, message)
            return message
        events = calendar_client.get_upcoming_events(
            gcal_service,
            intent.target_calendar,
            limit=intent.limit or 10,
        )
        message = calendar_client.format_upcoming_events(
            events,
            intent.target_calendar,
            intent.limit or 10,
        )
        _record_result(intent, message)
        return message

    if intent.action == IntentAction.CREATE_EVENT:
        command = {
            "cmd": "add",
            "calendar": intent.target_calendar,
            "calendar_display": intent.metadata.get("calendar_display", intent.target_calendar),
            "title": intent.title,
            "date": intent.target_date,
        }
        if intent.date_range is not None:
            command["end_date"] = intent.date_range.end
            command["all_day"] = True
        else:
            command["all_day"] = intent.metadata.get("all_day", intent.time_range is None)
        if intent.time_range is not None:
            command["start"] = intent.time_range.start
            command["end"] = intent.time_range.end
        if intent.recurrence:
            command["recurrence"] = list(intent.recurrence)
        message = calendar_client.add_event(gcal_service, command)
        _record_result(intent, message)
        return message

    if intent.action == IntentAction.UPDATE_EVENT:
        message = calendar_client.find_and_edit_event(
            gcal_service,
            intent.target_calendar,
            intent.target_date,
            intent.title,
            intent.changes,
        )
        _record_result(intent, message)
        return message

    if intent.action == IntentAction.DELETE_EVENT:
        message = calendar_client.find_and_delete_event(
            gcal_service,
            intent.target_calendar,
            intent.target_date,
            intent.title,
        )
        _record_result(intent, message)
        return message

    if intent.action == IntentAction.DELETE_SERIES:
        message = calendar_client.delete_recurring_series(
            gcal_service,
            intent.target_calendar,
            intent.title,
        )
        _record_result(intent, message)
        return message

    if intent.action == IntentAction.SEARCH:
        events = calendar_client.search_events(gcal_service, intent.search_query)
        message = calendar_client.format_search_results(events, intent.search_query)
        _record_result(intent, message)
        return message

    if intent.action == IntentAction.HELP:
        message = _help_reply(intent.help_topic)
        _record_result(intent, message)
        return message

    raise ValueError(f"Unsupported intent action: {intent.action}")


def _record_result(intent, message: str) -> None:
    result = ExecutionResult(
        success=not message.startswith("❌"),
        action=intent.action,
        message=message,
        metadata={
            "target_calendar": intent.target_calendar,
            "title": intent.title,
            "source": intent.source.value,
        },
    )
    state_store.record_execution(None, result)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("Molly starting up...")

    # Validate config before doing anything else
    config.validate()
    state_store.init_db()

    # Authenticate with the configured calendar backend once at startup
    global gcal_service
    log.info("Authenticating with calendar backend '%s'...", config.CALENDAR_BACKEND)
    gcal_service = calendar_client.authenticate()
    log.info("Calendar backend authentication successful.")

    # Build and start Telegram application
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start APScheduler (daily summary + per-event reminders)
    scheduler = sched_module.create_scheduler(gcal_service, app.bot)
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
