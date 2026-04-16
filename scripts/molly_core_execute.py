"""
Execute a structured Molly Core request once.

Usage:
  echo '{"action":"create_event",...}' | ./.venv/bin/python scripts/molly_core_execute.py
"""
from __future__ import annotations

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
    payload = json.load(sys.stdin)

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
