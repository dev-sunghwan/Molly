"""
Create one event through Molly Core using shell-friendly argv flags.

This script is designed for OpenClaw's `exec` tool usage, where passing a
simple command with explicit flags is easier than streaming JSON over stdin.
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
    parser = argparse.ArgumentParser(description="Create one event through Molly Core")
    parser.add_argument("--calendar", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", help="YYYY-MM-DD for timed multi-day events")
    parser.add_argument("--start", required=True, help="HH:MM")
    parser.add_argument("--end", required=True, help="HH:MM")
    parser.add_argument("--raw-input", default="")
    parser.add_argument("--nlu", default="openclaw")
    parser.add_argument("--request-source", default="openclaw_exec_tool")
    parser.add_argument("--actor-user-id", type=int)
    parser.add_argument(
        "--recurrence",
        action="append",
        default=[],
        help="Repeatable RRULE string, e.g. RRULE:FREQ=WEEKLY;BYDAY=FR",
    )
    parser.add_argument(
        "--weekly-day",
        choices=["MO", "TU", "WE", "TH", "FR", "SA", "SU"],
        help="Convenience alias for a weekly recurring event on one weekday",
    )
    args = parser.parse_args()

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
    if args.end_date:
        payload["end_date"] = args.end_date
    if recurrence:
        payload["recurrence"] = recurrence

    config.validate()
    state_store.init_db()
    calendar_repo = CalendarRepository.from_config()
    core = MollyCore(calendar_repo)
    resolution = resolution_from_request(payload)
    message = core.execute_resolution(resolution, user_id=args.actor_user_id)
    success = not message.startswith("❌")
    if args.actor_user_id is not None:
        try:
            import spouse_notifications

            spouse_notifications.notify_spouse_sync(args.actor_user_id, resolution.intent, success)
        except Exception:
            pass

    print(
        json.dumps(
            {
                "success": success,
                "action": resolution.intent.action.value,
                "message": message,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
