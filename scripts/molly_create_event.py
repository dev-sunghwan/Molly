"""
Legacy create-event CLI.

The canonical runtime entrypoint is now `scripts/molly_schedule_action.py
create`. This compatibility wrapper preserves older commands while keeping the
execution path in one place.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import molly_schedule_action  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create one event through Molly. Deprecated: use "
            "scripts/molly_schedule_action.py create for new integrations."
        )
    )
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
    parser.add_argument("--actor-name")
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
    parser.add_argument("--request-id", help="Stable inbound request id for command journaling")
    parser.add_argument("--source", default="openclaw", help="Inbound source")
    parser.add_argument("--source-message-id")
    parser.add_argument("--source-user-id")
    parser.add_argument("--source-user-name")
    parser.add_argument("--source-channel-id")
    args = parser.parse_args()

    delegated = [
        "molly_schedule_action.py",
        "create",
        "--calendar",
        args.calendar,
        "--title",
        args.title,
        "--date",
        args.date,
        "--start",
        args.start,
        "--end",
        args.end,
        "--raw-input",
        args.raw_input,
        "--nlu",
        args.nlu,
        "--request-source",
        args.request_source,
    ]
    _append_optional(delegated, "--end-date", args.end_date)
    _append_optional(delegated, "--actor-user-id", args.actor_user_id)
    _append_optional(delegated, "--actor-name", args.actor_name)
    _append_optional(delegated, "--request-id", args.request_id)
    _append_optional(delegated, "--source", args.source)
    _append_optional(delegated, "--source-message-id", args.source_message_id)
    _append_optional(delegated, "--source-user-id", args.source_user_id)
    _append_optional(delegated, "--source-user-name", args.source_user_name)
    _append_optional(delegated, "--source-channel-id", args.source_channel_id)
    for recurrence in args.recurrence or []:
        delegated.extend(["--recurrence", recurrence])
    _append_optional(delegated, "--weekly-day", args.weekly_day)

    original_argv = sys.argv
    try:
        sys.argv = delegated
        molly_schedule_action.main()
    finally:
        sys.argv = original_argv


def _append_optional(command: list[str], flag: str, value) -> None:
    if value is None:
        return
    text = str(value)
    if text:
        command.extend([flag, text])


if __name__ == "__main__":
    main()
