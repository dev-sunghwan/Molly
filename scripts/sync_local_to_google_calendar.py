"""
Sync Molly local calendar events into Google Calendar.

Stage 1 policy:
- local calendar is the source of truth
- only missing Google events are inserted
- no Google edits or deletes are performed
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

import calendar_sync
import config
import utils


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Molly local calendar events into Google Calendar.")
    parser.add_argument("--start", help="Start date in YYYY-MM-DD. Defaults to 30 days ago.")
    parser.add_argument("--end", help="End date in YYYY-MM-DD. Defaults to 180 days ahead.")
    parser.add_argument("--calendar", action="append", default=[], help="Calendar key or alias to sync. Repeatable.")
    parser.add_argument("--apply", action="store_true", help="Actually insert missing events into Google Calendar.")
    parser.add_argument("--details", type=int, default=20, help="How many detail lines to print.")
    args = parser.parse_args()

    today = utils._today_local()
    start_date = utils.parse_date(args.start) if args.start else (today - timedelta(days=30))
    end_date = utils.parse_date(args.end) if args.end else (today + timedelta(days=180))
    calendar_keys = _normalize_calendar_args(args.calendar)

    summary, details = calendar_sync.sync_local_to_google(
        start_date,
        end_date,
        dry_run=not args.apply,
        calendar_keys=calendar_keys,
    )

    print(json.dumps({
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "dry_run": not args.apply,
        "calendar_keys": calendar_keys,
        "inserted": summary.inserted,
        "skipped_existing": summary.skipped_existing,
        "skipped_unsupported": summary.skipped_unsupported,
        "details": details[: args.details],
    }, ensure_ascii=False, indent=2))


def _normalize_calendar_args(values: list[str]) -> list[str] | None:
    if not values:
        return None
    result: list[str] = []
    for value in values:
        key = config.normalize_calendar_name(value)
        if key is None:
            raise SystemExit(f"Unknown calendar: {value}")
        if key not in result:
            result.append(key)
    return result


if __name__ == "__main__":
    main()
