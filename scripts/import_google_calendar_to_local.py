"""
Import Google Calendar events into Molly's local calendar database.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import calendar_import
import utils


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Google Calendar events into Molly local storage.")
    parser.add_argument("--start", help="Start date in YYYY-MM-DD. Defaults to 180 days ago.")
    parser.add_argument("--end", help="End date in YYYY-MM-DD. Defaults to 365 days ahead.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be imported without writing.")
    parser.add_argument("--details", type=int, default=20, help="How many detail lines to print.")
    args = parser.parse_args()

    today = utils._today_local()
    start_date = utils.parse_date(args.start) if args.start else (today - timedelta(days=180))
    end_date = utils.parse_date(args.end) if args.end else (today + timedelta(days=365))

    summary, details = calendar_import.import_google_to_local(
        start_date,
        end_date,
        dry_run=args.dry_run,
    )

    print(
        json.dumps(
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "dry_run": args.dry_run,
                "imported": summary.imported,
                "skipped_duplicates": summary.skipped_duplicates,
                "skipped_unsupported": summary.skipped_unsupported,
                "skipped_cancelled": summary.skipped_cancelled,
                "details": details[: args.details],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
