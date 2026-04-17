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
from molly_core import MollyCore
from molly_core_requests import resolution_from_request
import state_store


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

    search_parser = subparsers.add_parser("search", help="Search events")
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument("--raw-input", default="")

    delete_parser = subparsers.add_parser("delete", help="Delete one event")
    delete_parser.add_argument("--calendar", required=True)
    delete_parser.add_argument("--title", required=True)
    delete_parser.add_argument("--date")
    delete_parser.add_argument("--raw-input", default="")

    update_parser = subparsers.add_parser("update", help="Update one event")
    update_parser.add_argument("--calendar", required=True)
    update_parser.add_argument("--title", required=True)
    update_parser.add_argument("--date")
    update_parser.add_argument("--new-title")
    update_parser.add_argument("--new-date")
    update_parser.add_argument("--start")
    update_parser.add_argument("--end")
    update_parser.add_argument("--raw-input", default="")

    args = parser.parse_args()

    payload = _payload_from_args(args)
    result = _execute_payload(payload)
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


def _execute_payload(payload: dict) -> dict:
    config.validate()
    state_store.init_db()
    calendar_repo = CalendarRepository.from_config()
    core = MollyCore(calendar_repo)
    resolution = resolution_from_request(payload)
    message = core.execute_resolution(resolution)
    return {
        "success": not message.startswith("❌"),
        "action": resolution.intent.action.value,
        "message": message,
    }


if __name__ == "__main__":
    main()
