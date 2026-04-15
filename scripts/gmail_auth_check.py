"""
scripts/gmail_auth_check.py — First-run Gmail authorization helper for Molly.

Usage:
  ./.venv/bin/python scripts/gmail_auth_check.py
  ./.venv/bin/python scripts/gmail_auth_check.py --list 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
import gmail_adapter
import gmail_client


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Authorize Molly's Gmail access and optionally list recent inbox messages."
    )
    parser.add_argument(
        "--list",
        type=int,
        default=0,
        metavar="N",
        help="after authorization, print the most recent N inbox messages",
    )
    args = parser.parse_args()

    print(f"Gmail account target: molly.kim.agent@gmail.com")
    print(f"Credentials file: {config.GMAIL_CREDENTIALS_PATH}")
    print(f"Gmail token file: {config.GMAIL_TOKEN_PATH}")
    print("Starting Gmail OAuth flow if needed...")

    service = gmail_client.authenticate()
    print("Gmail authentication successful.")

    if args.list > 0:
        message_ids = gmail_adapter.list_message_ids(service, max_results=args.list)
        print(f"Recent inbox messages: {len(message_ids)}")
        for message_id in message_ids:
            message = gmail_adapter.fetch_message(service, message_id)
            print(f"- {message.subject or '(no subject)'} | {message.sender}")


if __name__ == "__main__":
    main()
