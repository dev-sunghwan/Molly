"""
scripts/process_inbox_once.py — Process recent Molly inbox messages once.

Usage:
  ./.venv/bin/python scripts/process_inbox_once.py
  ./.venv/bin/python scripts/process_inbox_once.py --limit 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import gmail_client
import inbox_processor


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process a recent batch of Molly inbox messages once."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        metavar="N",
        help="number of recent inbox messages to scan",
    )
    args = parser.parse_args()

    service = gmail_client.authenticate()
    processed = inbox_processor.process_recent_inbox_messages(service, max_results=args.limit)
    print(inbox_processor.format_processing_report(processed))


if __name__ == "__main__":
    main()
