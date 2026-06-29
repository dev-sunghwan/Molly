"""
Drain Molly's Google Calendar sync outbox.

The worker keeps Google Calendar outside the Telegram response path. It can be
run once from cron/systemd timer or left in a small polling loop.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import calendar_sync  # noqa: E402
import config  # noqa: E402
import state_store  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(config.LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Molly Google sync outbox worker.")
    parser.add_argument("--once", action="store_true", help="Process one batch and exit.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview pending work without claiming rows.",
    )
    parser.add_argument("--limit", type=int, default=10, help="Maximum outbox rows per batch.")
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between batches in loop mode.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=5,
        help="Attempts before marking a row failed.",
    )
    args = parser.parse_args()

    config.validate()
    state_store.init_db()

    if args.once or args.dry_run:
        _run_batch(args.limit, args.max_attempts, args.dry_run)
        return

    log.info("Google sync worker started. interval=%ss limit=%s", args.interval, args.limit)
    try:
        while True:
            _run_batch(args.limit, args.max_attempts, dry_run=False)
            time.sleep(max(5, args.interval))
    except KeyboardInterrupt:
        log.info("Google sync worker stopped.")


def _run_batch(limit: int, max_attempts: int, dry_run: bool) -> None:
    summary, details = calendar_sync.process_google_sync_outbox_once(
        limit=limit,
        max_attempts=max_attempts,
        dry_run=dry_run,
    )
    payload = {
        "dry_run": dry_run,
        "processed": summary.processed,
        "inserted": summary.inserted,
        "skipped_existing": summary.skipped_existing,
        "unsupported": summary.unsupported,
        "failed": summary.failed,
        "details": details,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
