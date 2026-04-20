"""
Shell-friendly Molly scheduling fast-path actions for OpenClaw exec usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from calendar_repository import CalendarRepository
import config
import gmail_client
import gmail_confirmation
import inbox_processor
from molly_core import MollyCore
from molly_core_requests import resolution_from_request
import state_store
from telegram import Bot


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
    view_parser.add_argument("--scope", required=True, choices=["today", "tomorrow", "date", "next", "upcoming"])
    view_parser.add_argument("--calendar")
    view_parser.add_argument("--date")
    view_parser.add_argument("--limit", type=int)
    view_parser.add_argument("--raw-input", default="")
    view_parser.add_argument("--actor-user-id", type=int)
    view_parser.add_argument("--actor-name")

    search_parser = subparsers.add_parser("search", help="Search events")
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument("--raw-input", default="")
    search_parser.add_argument("--actor-user-id", type=int)
    search_parser.add_argument("--actor-name")

    delete_parser = subparsers.add_parser("delete", help="Delete one event")
    delete_parser.add_argument("--calendar", required=True)
    delete_parser.add_argument("--title", required=True)
    delete_parser.add_argument("--date")
    delete_parser.add_argument("--raw-input", default="")
    delete_parser.add_argument("--actor-user-id", type=int)
    delete_parser.add_argument("--actor-name")

    move_parser = subparsers.add_parser("move", help="Move one event between calendars")
    move_parser.add_argument("--from-calendar", required=True)
    move_parser.add_argument("--to-calendar", required=True)
    move_parser.add_argument("--title", required=True)
    move_parser.add_argument("--date")
    move_parser.add_argument("--raw-input", default="")
    move_parser.add_argument("--actor-user-id", type=int)
    move_parser.add_argument("--actor-name")

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

    payload = _payload_from_args(args)
    result = _execute_payload(
        payload,
        actor_user_id=getattr(args, "actor_user_id", None),
        actor_name=getattr(args, "actor_name", None),
    )
    print(json.dumps(result, ensure_ascii=False))


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
            "raw_input": args.raw_input,
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
