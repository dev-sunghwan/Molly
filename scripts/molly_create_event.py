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
    parser.add_argument("--start", required=True, help="HH:MM")
    parser.add_argument("--end", required=True, help="HH:MM")
    parser.add_argument("--raw-input", default="")
    parser.add_argument("--nlu", default="openclaw")
    parser.add_argument("--request-source", default="openclaw_exec_tool")
    args = parser.parse_args()

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

    config.validate()
    state_store.init_db()
    calendar_repo = CalendarRepository.from_config()
    core = MollyCore(calendar_repo)
    resolution = resolution_from_request(payload)
    message = core.execute_resolution(resolution)

    print(
        json.dumps(
            {
                "success": not message.startswith("❌"),
                "action": resolution.intent.action.value,
                "message": message,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
