"""
Legacy Gmail candidate CLI.

The canonical runtime entrypoint is now `scripts/molly_schedule_action.py`
with `gmail-*` subcommands. This wrapper keeps older operational commands
working while avoiding a second Gmail execution path.
"""
from __future__ import annotations

import argparse
import sys
from argparse import Namespace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import molly_schedule_action  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Manage Molly Gmail inbox candidates. Deprecated: use "
            "scripts/molly_schedule_action.py gmail-* for new integrations."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    process_parser = subparsers.add_parser("process", help="scan inbox and store Gmail candidates")
    process_parser.add_argument("--limit", type=int, default=5, metavar="N")
    process_parser.add_argument("--query", default="in:inbox")
    process_parser.add_argument("--notify", action="store_true")

    list_parser = subparsers.add_parser("list", help="list stored Gmail candidates")
    list_parser.add_argument("--state", default=None)
    list_parser.add_argument("--limit", type=int, default=20, metavar="N")

    confirm_parser = subparsers.add_parser(
        "confirm",
        help="confirm and execute one Gmail candidate",
    )
    confirm_parser.add_argument("--candidate-id", type=int, required=True)
    confirm_parser.add_argument("--actor-user-id", type=int, default=None)

    ignore_parser = subparsers.add_parser("ignore", help="ignore one Gmail candidate")
    ignore_parser.add_argument("--candidate-id", type=int, required=True)
    ignore_parser.add_argument("--actor-user-id", type=int, default=None)

    notify_parser = subparsers.add_parser(
        "notify-pending",
        help="send Telegram notifications for pending candidates",
    )
    notify_parser.add_argument("--limit", type=int, default=20, metavar="N")

    args = parser.parse_args()
    result = molly_schedule_action._execute_gmail_args(_canonical_args(args))
    print(result["message"])


def _canonical_args(args: argparse.Namespace) -> Namespace:
    return Namespace(
        subcommand=_canonical_subcommand(args.command),
        limit=getattr(args, "limit", None),
        query=getattr(args, "query", "in:inbox"),
        notify=getattr(args, "notify", False),
        state=getattr(args, "state", None),
        candidate_id=getattr(args, "candidate_id", None),
        actor_user_id=getattr(args, "actor_user_id", None),
        actor_name=None,
    )


def _canonical_subcommand(command: str) -> str:
    return {
        "process": "gmail-process",
        "list": "gmail-list",
        "confirm": "gmail-confirm",
        "ignore": "gmail-ignore",
        "notify-pending": "gmail-notify-pending",
    }[command]


if __name__ == "__main__":
    main()
