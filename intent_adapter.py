"""
intent_adapter.py — Translate existing Molly command dicts into shared intents.
"""
from __future__ import annotations

import config
import utils
from intent_models import (
    DateRange,
    IntentAction,
    IntentResolution,
    IntentSource,
    ResolutionStatus,
    ScheduleIntent,
    TimeRange,
)


def parse_text_to_intent(text: str, parser) -> IntentResolution:
    """Parse raw text with an existing parser and translate it into a shared intent."""
    command = parser(text)
    if "error" in command:
        inferred = infer_intent_from_text(text)
        if inferred is not None:
            return inferred
    return command_to_intent(command, raw_input=text)


def command_to_intent(command: dict, raw_input: str = "") -> IntentResolution:
    """
    Convert an existing commands.parse() output dict into a ScheduleIntent.
    The resulting resolution boundary becomes the handoff between interpretation
    and deterministic execution.
    """
    if "error" in command:
        intent = ScheduleIntent(
            action=IntentAction.HELP,
            source=IntentSource.TELEGRAM_COMMAND,
            raw_input=raw_input,
            metadata={"parse_error": command["error"]},
        )
        return IntentResolution(
            status=ResolutionStatus.INVALID,
            intent=intent,
            reason=command["error"],
        )

    cmd = command["cmd"]

    if cmd in {"today", "tomorrow", "date"}:
        target_date = command.get("date")
        if cmd == "today":
            target_date = None
        elif cmd == "tomorrow":
            target_date = None

        intent = ScheduleIntent(
            action=IntentAction.VIEW_DAILY,
            source=IntentSource.TELEGRAM_COMMAND,
            raw_input=raw_input,
            target_date=target_date,
            metadata={"command": cmd},
        )
        return _ready(intent)

    if cmd in {"week", "week_next", "month", "month_next", "upcoming", "next"}:
        action = IntentAction.VIEW_RANGE
        intent = ScheduleIntent(
            action=action,
            source=IntentSource.TELEGRAM_COMMAND,
            raw_input=raw_input,
            target_calendar=command.get("calendar"),
            limit=command.get("limit"),
            metadata={"command": cmd},
        )
        return _ready(intent)

    if cmd == "add":
        intent = ScheduleIntent(
            action=IntentAction.CREATE_EVENT,
            source=IntentSource.TELEGRAM_COMMAND,
            raw_input=raw_input,
            target_calendar=command["calendar"],
            title=command["title"],
            target_date=command.get("date"),
            time_range=_maybe_time_range(command),
            recurrence=list(command.get("recurrence", [])),
            metadata={
                "all_day": command.get("all_day", False),
                "calendar_display": command.get("calendar_display"),
            },
        )
        if "end_date" in command:
            intent.date_range = DateRange(start=command["date"], end=command["end_date"])
        return validate_intent(intent)

    if cmd == "edit":
        intent = ScheduleIntent(
            action=IntentAction.UPDATE_EVENT,
            source=IntentSource.TELEGRAM_COMMAND,
            raw_input=raw_input,
            target_calendar=command["calendar"],
            title=command["title"],
            target_date=command.get("date"),
            changes=dict(command.get("changes", {})),
            metadata={"command": cmd},
        )
        return validate_intent(intent)

    if cmd == "delete":
        intent = ScheduleIntent(
            action=IntentAction.DELETE_EVENT,
            source=IntentSource.TELEGRAM_COMMAND,
            raw_input=raw_input,
            target_calendar=command["calendar"],
            title=command["title"],
            target_date=command.get("date"),
            metadata={"command": cmd},
        )
        return validate_intent(intent)

    if cmd == "delete_all":
        intent = ScheduleIntent(
            action=IntentAction.DELETE_SERIES,
            source=IntentSource.TELEGRAM_COMMAND,
            raw_input=raw_input,
            target_calendar=command["calendar"],
            title=command["title"],
            metadata={"command": cmd},
        )
        return validate_intent(intent)

    if cmd == "search":
        intent = ScheduleIntent(
            action=IntentAction.SEARCH,
            source=IntentSource.TELEGRAM_COMMAND,
            raw_input=raw_input,
            search_query=command["keyword"],
            metadata={"command": cmd},
        )
        return validate_intent(intent)

    if cmd == "help":
        intent = ScheduleIntent(
            action=IntentAction.HELP,
            source=IntentSource.TELEGRAM_COMMAND,
            raw_input=raw_input,
            help_topic=command.get("topic"),
            metadata={"command": cmd},
        )
        return _ready(intent)

    raise ValueError(f"Unsupported command for intent translation: {cmd}")


def validate_intent(intent: ScheduleIntent) -> IntentResolution:
    """Validate required fields for a shared intent."""
    missing: list[str] = []

    if intent.action in {
        IntentAction.CREATE_EVENT,
        IntentAction.UPDATE_EVENT,
        IntentAction.DELETE_EVENT,
        IntentAction.DELETE_SERIES,
    } and not intent.target_calendar:
        missing.append("target_calendar")

    if intent.action in {
        IntentAction.CREATE_EVENT,
        IntentAction.UPDATE_EVENT,
        IntentAction.DELETE_EVENT,
        IntentAction.DELETE_SERIES,
    } and not intent.title:
        missing.append("title")

    if intent.action == IntentAction.SEARCH and not intent.search_query:
        missing.append("search_query")

    if missing:
        return IntentResolution(
            status=ResolutionStatus.NEEDS_CLARIFICATION,
            intent=intent,
            missing_fields=missing,
            clarification_prompt=_clarification_prompt(missing),
        )

    return _ready(intent)


def _ready(intent: ScheduleIntent) -> IntentResolution:
    return IntentResolution(status=ResolutionStatus.READY, intent=intent)


def _maybe_time_range(command: dict) -> TimeRange | None:
    start = command.get("start")
    end = command.get("end")
    if start and end:
        return TimeRange(start=start, end=end)
    return None


def _clarification_prompt(missing_fields: list[str]) -> str:
    if missing_fields == ["target_calendar"]:
        return "Which family calendar should Molly use?"
    if missing_fields == ["title"]:
        return "What event title should Molly use?"
    return "Molly needs more information before it can continue."


def infer_intent_from_text(text: str) -> IntentResolution | None:
    """
    Best-effort inference for simple command-like requests that are missing the
    target calendar. This provides the Phase 2 clarification entry point.
    """
    stripped = text.strip()
    lower = stripped.lower()
    if lower.startswith("add "):
        return _infer_add_without_calendar(stripped)
    return None


def _infer_add_without_calendar(text: str) -> IntentResolution | None:
    """
    Infer an add-event intent when the user omitted the calendar name.
    Supported layouts mirror the existing command parser minus the calendar:
      add <title> <date> <time>
      add <title> <time>
      add <title> <date>
      add <title>
      add <title> <date> to <date>
      add <title> every <day> [<time>]
    """
    rest = text[4:].strip()
    tokens = rest.split()
    if not tokens:
        return None

    lower_tokens = [token.lower() for token in tokens]

    if "every" in lower_tokens:
        return _infer_add_without_calendar_recurring(tokens)

    if "to" in lower_tokens:
        to_idx = lower_tokens.index("to")
        if 0 < to_idx < len(tokens) - 1:
            start_date = utils.parse_date(tokens[to_idx - 1].lower())
            end_date = utils.parse_date(tokens[to_idx + 1].lower())
            if start_date is not None and end_date is not None:
                title = " ".join(tokens[: to_idx - 1]).strip()
                intent = ScheduleIntent(
                    action=IntentAction.CREATE_EVENT,
                    source=IntentSource.TELEGRAM_FREE_TEXT,
                    raw_input=text,
                    title=title or None,
                    target_date=start_date,
                    date_range=DateRange(start=start_date, end=end_date),
                    metadata={"all_day": True, "inferred_missing_calendar": True},
                )
                return validate_intent(intent)

    last = tokens[-1]
    last_is_time = utils.parse_time(last) is not None
    last_is_date = utils.parse_date(last.lower()) is not None

    if last_is_time:
        if len(tokens) >= 3 and utils.parse_date(tokens[-2].lower()) is not None:
            event_date = utils.parse_date(tokens[-2].lower())
            title_tokens = tokens[:-2]
        else:
            event_date = utils._today_local()
            title_tokens = tokens[:-1]

        start_time, end_time = utils.parse_time(last)
        intent = ScheduleIntent(
            action=IntentAction.CREATE_EVENT,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input=text,
            title=" ".join(title_tokens).strip() or None,
            target_date=event_date,
            time_range=TimeRange(start=start_time, end=end_time),
            metadata={"all_day": False, "inferred_missing_calendar": True},
        )
        return validate_intent(intent)

    if last_is_date:
        intent = ScheduleIntent(
            action=IntentAction.CREATE_EVENT,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input=text,
            title=" ".join(tokens[:-1]).strip() or None,
            target_date=utils.parse_date(last.lower()),
            metadata={"all_day": True, "inferred_missing_calendar": True},
        )
        return validate_intent(intent)

    intent = ScheduleIntent(
        action=IntentAction.CREATE_EVENT,
        source=IntentSource.TELEGRAM_FREE_TEXT,
        raw_input=text,
        title=" ".join(tokens).strip() or None,
        target_date=utils._today_local(),
        metadata={"all_day": True, "inferred_missing_calendar": True},
    )
    return validate_intent(intent)


def _infer_add_without_calendar_recurring(tokens: list[str]) -> IntentResolution | None:
    lower_tokens = [token.lower() for token in tokens]
    every_idx = lower_tokens.index("every")
    title = " ".join(tokens[:every_idx]).strip()
    after_every = tokens[every_idx + 1 :]
    if not title or not after_every:
        return None

    day_token = after_every[0]
    rrule_day = utils.day_name_to_rrule(day_token)
    if rrule_day is None:
        return None

    recurrence = [f"RRULE:FREQ=WEEKLY;BYDAY={rrule_day}"]
    target_date = utils.parse_date(day_token.lower())
    time_range = None
    if len(after_every) >= 2:
        parsed_time = utils.parse_time(after_every[-1])
        if parsed_time is None:
            return None
        time_range = TimeRange(start=parsed_time[0], end=parsed_time[1])

    intent = ScheduleIntent(
        action=IntentAction.CREATE_EVENT,
        source=IntentSource.TELEGRAM_FREE_TEXT,
        raw_input="add " + " ".join(tokens),
        title=title,
        target_date=target_date,
        time_range=time_range,
        recurrence=recurrence,
        metadata={"all_day": time_range is None, "inferred_missing_calendar": True},
    )
    return validate_intent(intent)
