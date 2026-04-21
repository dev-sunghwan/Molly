"""
scripts/molly_gmail_action.py — Gmail inbox candidate actions for Molly.

Usage examples:
  ./.venv/bin/python scripts/molly_gmail_action.py process --limit 5 --notify
  ./.venv/bin/python scripts/molly_gmail_action.py list
  ./.venv/bin/python scripts/molly_gmail_action.py confirm --candidate-id 3
  ./.venv/bin/python scripts/molly_gmail_action.py ignore --candidate-id 3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from telegram import Bot

from calendar_repository import CalendarRepository
import config
import gmail_client
import gmail_confirmation
import inbox_processor
import state_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Molly Gmail inbox candidates.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    process_parser = subparsers.add_parser("process", help="scan inbox and store Gmail candidates")
    process_parser.add_argument("--limit", type=int, default=5, metavar="N")
    process_parser.add_argument("--query", default="in:inbox")
    process_parser.add_argument("--notify", action="store_true")

    list_parser = subparsers.add_parser("list", help="list stored Gmail candidates")
    list_parser.add_argument("--state", default=None)
    list_parser.add_argument("--limit", type=int, default=20, metavar="N")

    confirm_parser = subparsers.add_parser("confirm", help="confirm and execute one Gmail candidate")
    confirm_parser.add_argument("--candidate-id", type=int, required=True)
    confirm_parser.add_argument("--actor-user-id", type=int, default=None)

    ignore_parser = subparsers.add_parser("ignore", help="ignore one Gmail candidate")
    ignore_parser.add_argument("--candidate-id", type=int, required=True)
    ignore_parser.add_argument("--actor-user-id", type=int, default=None)

    notify_parser = subparsers.add_parser("notify-pending", help="send Telegram notifications for pending candidates")
    notify_parser.add_argument("--limit", type=int, default=20, metavar="N")

    args = parser.parse_args()

    state_store.init_db()

    if args.command == "process":
        service = gmail_client.authenticate()
        processed = inbox_processor.process_recent_inbox_messages(
            service,
            max_results=args.limit,
            query=args.query,
        )
        print(inbox_processor.format_processing_report(processed))
        if args.notify:
            bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            sent = gmail_confirmation.notify_pending_candidates(bot, limit=args.limit)
            print(f"\nSent Gmail candidate notifications: {len(sent)}")
        return

    if args.command == "list":
        print(gmail_confirmation.list_candidate_summaries(args.state, limit=args.limit))
        return

    if args.command == "confirm":
        calendar_repo = CalendarRepository.from_config()
        print(
            gmail_confirmation.confirm_candidate(
                args.candidate_id,
                calendar_repo,
                actor_user_id=args.actor_user_id,
            )
        )
        return

    if args.command == "ignore":
        print(
            gmail_confirmation.ignore_candidate(
                args.candidate_id,
                actor_user_id=args.actor_user_id,
            )
        )
        return

    if args.command == "notify-pending":
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        sent = gmail_confirmation.notify_pending_candidates(bot, limit=args.limit)
        print(f"Sent Gmail candidate notifications: {len(sent)}")
        return


if __name__ == "__main__":
    main()
