"""
Shell-friendly Molly scheduling fast-path actions for OpenClaw exec usage.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from telegram import Bot

import commands
import config
import gmail_client
import gmail_confirmation
import inbox_processor
import state_store
import utils
from calendar_repository import CalendarRepository
from intent_adapter import command_to_intent
import telegram_nlu
from intent_models import ResolutionStatus
from molly_core import MollyCore
from molly_core_requests import resolution_from_request

_MUTATING_PAYLOAD_ACTIONS = {
    "create_event",
    "update_event",
    "delete_event",
    "move_event",
    "delete_series",
}
_REQUEST_ID_REQUIRED_SUBCOMMANDS = {
    "command",
    "create",
    "delete",
    "move",
    "update",
}


def _add_journal_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--request-id", help="Stable inbound request id for command journaling")
    parser.add_argument("--source", default="openclaw", help="Inbound source, e.g. telegram, slack, openclaw")
    parser.add_argument("--source-message-id")
    parser.add_argument("--source-user-id")
    parser.add_argument("--source-user-name")
    parser.add_argument("--source-channel-id")


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute Molly scheduling fast-path actions.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    create_parser = subparsers.add_parser("create", help="Create one event")
    create_parser.add_argument("--calendar", required=True)
    create_parser.add_argument("--title", required=True)
    create_parser.add_argument("--date", required=True)
    create_parser.add_argument("--end-date")
    create_parser.add_argument("--start", required=True)
    create_parser.add_argument("--end")
    create_parser.add_argument("--raw-input", default="")
    create_parser.add_argument("--nlu", default="openclaw")
    create_parser.add_argument("--request-source", default="openclaw_exec_tool")
    create_parser.add_argument("--actor-user-id", type=int)
    create_parser.add_argument("--actor-name")
    _add_journal_args(create_parser)
    create_parser.add_argument(
        "--recurrence",
        action="append",
        default=[],
        help="Repeatable RRULE string, e.g. RRULE:FREQ=WEEKLY;BYDAY=FR",
    )
    create_parser.add_argument(
        "--weekly-day",
        choices=["MO", "TU", "WE", "TH", "FR", "SA", "SU"],
        help="Convenience alias for a weekly recurring event on one weekday",
    )

    view_parser = subparsers.add_parser("view", help="View events")
    view_parser.add_argument("--scope", required=True, choices=["today", "tomorrow", "date", "next", "upcoming", "week", "week_next", "month", "month_remaining", "month_next"])
    view_parser.add_argument("--calendar")
    view_parser.add_argument("--date")
    view_parser.add_argument("--limit", type=int)
    view_parser.add_argument("--raw-input", default="")
    view_parser.add_argument("--actor-user-id", type=int)
    view_parser.add_argument("--actor-name")
    _add_journal_args(view_parser)

    command_parser = subparsers.add_parser("command", help="Execute a canonical Molly core command directly")
    command_parser.add_argument("--text", required=True, help="Canonical Molly command text, e.g. 'today', 'week', 'upcoming YounHa 5'")
    command_parser.add_argument("--actor-user-id", type=int)
    command_parser.add_argument("--actor-name")
    _add_journal_args(command_parser)

    search_parser = subparsers.add_parser("search", help="Search events")
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument("--raw-input", default="")
    search_parser.add_argument("--actor-user-id", type=int)
    search_parser.add_argument("--actor-name")
    _add_journal_args(search_parser)

    delete_parser = subparsers.add_parser("delete", help="Delete one event")
    delete_parser.add_argument("--calendar", required=True)
    delete_parser.add_argument("--title", required=True)
    delete_parser.add_argument("--date")
    delete_parser.add_argument("--raw-input", default="")
    delete_parser.add_argument("--actor-user-id", type=int)
    delete_parser.add_argument("--actor-name")
    _add_journal_args(delete_parser)

    move_parser = subparsers.add_parser("move", help="Move one event between calendars")
    move_parser.add_argument("--from-calendar", required=True)
    move_parser.add_argument("--to-calendar", required=True)
    move_parser.add_argument("--title", required=True)
    move_parser.add_argument("--date")
    move_parser.add_argument("--raw-input", default="")
    move_parser.add_argument("--actor-user-id", type=int)
    move_parser.add_argument("--actor-name")
    _add_journal_args(move_parser)

    update_parser = subparsers.add_parser("update", help="Update one event")
    update_parser.add_argument("--calendar", required=True)
    update_parser.add_argument("--title", required=True)
    update_parser.add_argument("--date")
    update_parser.add_argument("--new-title")
    update_parser.add_argument("--new-date")
    update_parser.add_argument("--start")
    update_parser.add_argument("--end")
    update_parser.add_argument("--raw-input", default="")
    update_parser.add_argument("--actor-user-id", type=int)
    update_parser.add_argument("--actor-name")
    _add_journal_args(update_parser)

    gmail_process_parser = subparsers.add_parser("gmail-process", help="Process Gmail inbox candidates")
    gmail_process_parser.add_argument("--limit", type=int, default=5)
    gmail_process_parser.add_argument("--query", default="in:inbox")
    gmail_process_parser.add_argument("--notify", action="store_true")
    gmail_process_parser.add_argument("--actor-user-id", type=int)
    gmail_process_parser.add_argument("--actor-name")

    gmail_list_parser = subparsers.add_parser("gmail-list", help="List Gmail candidates")
    gmail_list_parser.add_argument("--state", default=None)
    gmail_list_parser.add_argument("--limit", type=int, default=20)
    gmail_list_parser.add_argument("--actor-user-id", type=int)
    gmail_list_parser.add_argument("--actor-name")

    gmail_confirm_parser = subparsers.add_parser("gmail-confirm", help="Confirm one Gmail candidate")
    gmail_confirm_parser.add_argument("--candidate-id", type=int, required=True)
    gmail_confirm_parser.add_argument("--actor-user-id", type=int)
    gmail_confirm_parser.add_argument("--actor-name")

    gmail_ignore_parser = subparsers.add_parser("gmail-ignore", help="Ignore one Gmail candidate")
    gmail_ignore_parser.add_argument("--candidate-id", type=int, required=True)
    gmail_ignore_parser.add_argument("--actor-user-id", type=int)
    gmail_ignore_parser.add_argument("--actor-name")

    args = parser.parse_args()

    if args.subcommand.startswith("gmail-"):
        result = _execute_gmail_args(args)
        print(json.dumps(result, ensure_ascii=False))
        return

    if args.subcommand == "command":
        request_id = _journal_args(
            args,
            raw_text=args.text,
            raw_payload=_raw_payload_from_args(args),
        )
        result = _execute_with_journal(
            request_id,
            lambda: _execute_command_text(
                args.text,
                actor_user_id=getattr(args, "actor_user_id", None),
                actor_name=getattr(args, "actor_name", None),
            ),
            explicit_request_id=args.request_id,
            request_id_required=args.subcommand in _REQUEST_ID_REQUIRED_SUBCOMMANDS,
        )
        print(json.dumps(result, ensure_ascii=False))
        return

    payload = _payload_from_args(args)
    request_id = _journal_args(
        args,
        raw_text=payload.get("raw_input"),
        raw_payload=payload,
    )
    result = _execute_with_journal(
        request_id,
        lambda: _execute_payload(
            payload,
            actor_user_id=getattr(args, "actor_user_id", None),
            actor_name=getattr(args, "actor_name", None),
        ),
        structured_payload=payload,
        explicit_request_id=args.request_id,
        request_id_required=args.subcommand in _REQUEST_ID_REQUIRED_SUBCOMMANDS,
    )
    print(json.dumps(result, ensure_ascii=False))


def _journal_enabled() -> bool:
    return os.getenv("MOLLY_COMMAND_JOURNAL_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _raw_payload_from_args(args: argparse.Namespace) -> dict:
    return {
        key: value
        for key, value in vars(args).items()
        if key
        not in {
            "request_id",
            "source",
            "source_message_id",
            "source_user_id",
            "source_user_name",
            "source_channel_id",
        }
    }


def _journal_args(
    args: argparse.Namespace,
    *,
    raw_text: str | None,
    raw_payload: dict,
) -> str | None:
    if not _journal_enabled():
        return None

    request_id = args.request_id or f"molly-cli-{uuid.uuid4()}"
    try:
        state_store.init_db()
        state_store.record_inbound_command(
            request_id=request_id,
            source=args.source,
            source_message_id=args.source_message_id,
            source_user_id=args.source_user_id
            or _optional_string(getattr(args, "actor_user_id", None)),
            source_user_name=args.source_user_name
            or _optional_string(getattr(args, "actor_name", None)),
            source_channel_id=args.source_channel_id,
            raw_text=raw_text,
            raw_payload=raw_payload,
        )
        return request_id
    except Exception as exc:
        print(
            f"[molly_schedule_action] command journal write failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None


def _execute_with_journal(
    request_id: str | None,
    runner,
    *,
    structured_payload: dict | None = None,
    explicit_request_id: str | None = None,
    request_id_required: bool = False,
) -> dict:
    completed_result = _completed_result_for_request(request_id)
    if completed_result is not None:
        return completed_result

    try:
        _enforce_request_id_policy(
            explicit_request_id,
            structured_payload=structured_payload,
            request_id_required=request_id_required,
        )
        _update_journal_best_effort(request_id, "parsing")
        if structured_payload is not None:
            _update_journal_best_effort(
                request_id,
                "validated",
                structured_payload=structured_payload,
            )
        _update_journal_best_effort(request_id, "executing")
        result = runner()
    except ValueError as exc:
        _update_journal_best_effort(
            request_id,
            "rejected",
            validation_error=str(exc),
            execution_result={"success": False, "error": f"{type(exc).__name__}: {exc}"},
        )
        raise
    except Exception as exc:
        _update_journal_best_effort(
            request_id,
            "failed",
            execution_result={"success": False, "error": f"{type(exc).__name__}: {exc}"},
        )
        raise

    _update_journal_best_effort(
        request_id,
        "executed" if result.get("success") else "failed",
        execution_result=result,
    )
    return result


def _enforce_request_id_policy(
    explicit_request_id: str | None,
    *,
    structured_payload: dict | None,
    request_id_required: bool,
) -> None:
    if not config.REQUIRE_REQUEST_ID_FOR_MUTATIONS:
        return
    action = str((structured_payload or {}).get("action") or "")
    requires_id = request_id_required or action in _MUTATING_PAYLOAD_ACTIONS
    if not requires_id:
        return
    if explicit_request_id:
        return
    raise ValueError(
        "Stable request_id is required for mutating Molly requests when "
        "MOLLY_REQUIRE_REQUEST_ID_FOR_MUTATIONS=1"
    )


def _completed_result_for_request(request_id: str | None) -> dict | None:
    if request_id is None or not _journal_enabled():
        return None
    try:
        stored = state_store.get_command_by_request_id(request_id)
    except Exception as exc:
        print(
            f"[molly_schedule_action] command journal replay check failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None
    if stored is None or stored["status"] != "executed":
        return None
    result = stored.get("execution_result")
    return result if isinstance(result, dict) else None


def _update_journal_best_effort(
    request_id: str | None,
    status: str,
    *,
    structured_payload: dict | None = None,
    validation_error: str | None = None,
    execution_result: dict | None = None,
) -> None:
    if request_id is None or not _journal_enabled():
        return
    try:
        state_store.update_command_status(
            request_id,
            status,
            structured_payload=structured_payload,
            validation_error=validation_error,
            execution_result=execution_result,
        )
    except Exception as exc:
        print(
            f"[molly_schedule_action] command journal update failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )


def _optional_string(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _payload_from_args(args: argparse.Namespace) -> dict:
    if args.subcommand == "create":
        recurrence = list(args.recurrence or [])
        if args.weekly_day:
            recurrence.append(f"RRULE:FREQ=WEEKLY;BYDAY={args.weekly_day}")
        payload = {
            "action": "create_event",
            "target_calendar": args.calendar,
            "title": args.title,
            "target_date": args.date,
            "start_time": args.start,
            "end_time": args.end,
            "all_day": False,
            "raw_input": args.raw_input,
            "nlu": args.nlu,
            "request_source": args.request_source,
        }
        if recurrence:
            payload["recurrence"] = recurrence
        if args.end_date:
            payload["end_date"] = args.end_date
        return payload
    if args.subcommand == "view":
        payload = {
            "action": "view",
            "scope": args.scope,
            "raw_input": args.raw_input or args.scope.replace("_", " "),
        }
        if args.calendar:
            payload["target_calendar"] = args.calendar
        if args.date:
            payload["target_date"] = args.date
        if args.limit is not None:
            payload["limit"] = args.limit
        return payload
    if args.subcommand == "search":
        return {
            "action": "search",
            "query": args.query,
            "raw_input": args.raw_input,
        }
    if args.subcommand == "delete":
        payload = {
            "action": "delete_event",
            "target_calendar": args.calendar,
            "title": args.title,
            "raw_input": args.raw_input,
        }
        if args.date:
            payload["target_date"] = args.date
        return payload
    if args.subcommand == "move":
        payload = {
            "action": "move_event",
            "source_calendar": args.from_calendar,
            "target_calendar": args.to_calendar,
            "title": args.title,
            "raw_input": args.raw_input,
        }
        if args.date:
            payload["target_date"] = args.date
        return payload
    if args.subcommand == "update":
        changes: dict[str, str] = {}
        if args.new_title:
            changes["title"] = args.new_title
        if args.new_date:
            changes["target_date"] = args.new_date
        if args.start or args.end:
            if not (args.start and args.end):
                raise SystemExit("--start and --end must be provided together for update")
            changes["start_time"] = args.start
            changes["end_time"] = args.end
        return {
            "action": "update_event",
            "target_calendar": args.calendar,
            "title": args.title,
            "target_date": args.date,
            "changes": changes,
            "raw_input": args.raw_input,
        }
    raise SystemExit(f"Unsupported subcommand: {args.subcommand}")


def _execute_gmail_args(args: argparse.Namespace) -> dict:
    config.validate()
    state_store.init_db()

    if args.subcommand == "gmail-process":
        service = gmail_client.authenticate()
        processed = inbox_processor.process_recent_inbox_messages(
            service,
            max_results=args.limit,
            query=args.query,
        )
        notification_count = 0
        if args.notify:
            bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            notification_count = len(
                gmail_confirmation.notify_pending_candidates(bot, limit=args.limit)
            )
        return {
            "success": True,
            "action": "gmail_process",
            "message": inbox_processor.format_processing_report(processed),
            "processed_count": len(processed),
            "notification_count": notification_count,
        }

    if args.subcommand == "gmail-list":
        return {
            "success": True,
            "action": "gmail_list",
            "message": gmail_confirmation.list_candidate_summaries(args.state, limit=args.limit),
        }

    if args.subcommand == "gmail-confirm":
        calendar_repo = CalendarRepository.from_config()
        message = gmail_confirmation.confirm_candidate(
            args.candidate_id,
            calendar_repo,
            actor_user_id=args.actor_user_id,
        )
        return {
            "success": not message.startswith("❌"),
            "action": "gmail_confirm",
            "message": message,
        }

    if args.subcommand == "gmail-ignore":
        message = gmail_confirmation.ignore_candidate(
            args.candidate_id,
            actor_user_id=args.actor_user_id,
        )
        return {
            "success": not message.startswith("❌"),
            "action": "gmail_ignore",
            "message": message,
        }

    raise SystemExit(f"Unsupported Gmail subcommand: {args.subcommand}")





def _parse_short_or_full_date(token: str):
    parsed = utils.parse_date(token)
    if parsed is not None:
        return parsed
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", token.strip())
    if not m:
        return None
    day = int(m.group(1))
    month = int(m.group(2))
    today = utils._today_local()
    year = today.year
    from datetime import date as _date
    try:
        candidate = _date(year, month, day)
    except ValueError:
        return None
    return candidate


def _parse_flexible_delete_command(text: str, actor_user_id: int | None) -> dict | None:
    stripped = " ".join(text.replace("\n", " ").split())
    lowered = stripped.lower()
    if lowered.startswith("delete "):
        body = stripped[7:].strip()
    elif lowered.startswith("remove "):
        body = stripped[7:].strip()
    else:
        return None

    calendar = None
    bracket_match = re.search(r"\[([^\]]+)\]", body)
    if bracket_match:
        calendar = config.normalize_calendar_name(bracket_match.group(1))

    body_wo_bracket = re.sub(r"\[[^\]]+\]", " ", body)
    tokens = body_wo_bracket.split()
    if calendar is None and tokens:
        maybe_calendar = config.normalize_calendar_name(tokens[0])
        if maybe_calendar is not None:
            calendar = maybe_calendar
            body_wo_bracket = body_wo_bracket[len(tokens[0]):].strip()

    date_match = re.search(r"\bon\s+(\d{1,2}-\d{1,2}(?:-\d{4})?)\b", body_wo_bracket, flags=re.IGNORECASE)
    date_token = date_match.group(1) if date_match else None
    if date_token is None:
        lead_match = re.search(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2}-\d{1,2}(?:-\d{4})?)\b", body_wo_bracket, flags=re.IGNORECASE)
        if lead_match:
            date_token = lead_match.group(1)
    if date_token is None:
        plain_match = re.search(r"\b(\d{1,2}-\d{1,2}(?:-\d{4})?)\b", body_wo_bracket)
        if plain_match:
            date_token = plain_match.group(1)
    event_date = _parse_short_or_full_date(date_token) if date_token else None

    time_match = re.search(r"\b(\d{1,2}:\d{2})(?:\s*[–-]\s*\d{1,2}:\d{2})?\b", body_wo_bracket)
    start_time = None
    if time_match:
        parsed_time = utils.parse_time(time_match.group(0).replace(" ", ""))
        if parsed_time is not None:
            start_time = parsed_time[0]

    title = body_wo_bracket
    title = re.sub(r"\bon\s+\d{1,2}-\d{1,2}(?:-\d{4})?\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}-\d{1,2}(?:-\d{4})?\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\b\d{1,2}-\d{1,2}(?:-\d{4})?\b", " ", title)
    title = re.sub(r"\b\d{1,2}:\d{2}(?:\s*[–-]\s*\d{1,2}:\d{2})?\b", " ", title)
    title = re.sub(r"\b(the|event)\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"[•,]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        title = None

    if calendar is None and title is None and event_date is None and start_time is None:
        return None

    return {
        "cmd": "delete",
        "calendar": calendar,
        "date": event_date,
        "title": title,
        "start": start_time,
    }

def _execute_command_text(
    text: str,
    actor_user_id: int | None = None,
    actor_name: str | None = None,
) -> dict:
    config.validate()
    state_store.init_db()
    calendar_repo = CalendarRepository.from_config()
    core = MollyCore(calendar_repo)

    command = commands.parse(text)
    lowered_text = text.strip().lower()
    if lowered_text.startswith(("delete ", "remove ")):
        flexible_delete = _parse_flexible_delete_command(text, actor_user_id)
        if flexible_delete is not None:
            command = flexible_delete

    if command.get('cmd') == 'delete' and (command.get('start') or command.get('title')) and not command.get('calendar'):
        return {
            'success': False,
            'action': 'delete_event',
            'message': 'Which calendar should I delete it from?'
        }

    if command.get('cmd') == 'delete' and (command.get('start') or command.get('title')) and command.get('calendar'):
        message = calendar_repo.find_and_delete_event(
            command['calendar'],
            command.get('date'),
            command.get('title'),
            start_time=command.get('start'),
        )
        success = not message.startswith('❌')
        return {
            'success': success,
            'action': 'delete_event',
            'message': message,
        }

    resolution = command_to_intent(command, raw_input=text)
    if resolution.status != ResolutionStatus.READY:
        natural_language_resolution = telegram_nlu.parse_free_text_to_intent(text)
        if natural_language_resolution is not None:
            resolution = natural_language_resolution
        else:
            message = resolution.clarification_prompt or resolution.reason or "❌ Molly could not resolve that command"
            return {
                "success": False,
                "action": resolution.intent.action.value,
                "message": message,
            }

    message = core.execute_resolution(resolution, user_id=actor_user_id)
    success = not message.startswith("❌")
    if actor_user_id is not None or actor_name:
        try:
            import spouse_notifications

            spouse_notifications.notify_spouse_sync(
                actor_user_id,
                resolution.intent,
                success,
                actor_name=actor_name,
            )
        except Exception as exc:
            print(
                f"[molly_schedule_action] spouse notification failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
    return {
        "success": success,
        "action": resolution.intent.action.value,
        "message": message,
    }

def _execute_payload(
    payload: dict,
    actor_user_id: int | None = None,
    actor_name: str | None = None,
) -> dict:
    config.validate()
    state_store.init_db()
    calendar_repo = CalendarRepository.from_config()
    core = MollyCore(calendar_repo)
    resolution = resolution_from_request(payload)
    message = core.execute_resolution(resolution, user_id=actor_user_id)
    success = not message.startswith("❌")
    if actor_user_id is not None or actor_name:
        try:
            import spouse_notifications

            spouse_notifications.notify_spouse_sync(
                actor_user_id,
                resolution.intent,
                success,
                actor_name=actor_name,
            )
        except Exception as exc:
            print(
                f"[molly_schedule_action] spouse notification failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
    return {
        "success": success,
        "action": resolution.intent.action.value,
        "message": message,
    }


if __name__ == "__main__":
    main()
