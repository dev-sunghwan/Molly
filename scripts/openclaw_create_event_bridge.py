"""
Legacy one-shot OpenClaw create-event bridge.

Current live Telegram/Slack operation should call `scripts/molly_schedule_action.py`
directly through OpenClaw exec instructions. This script remains as a narrow
compatibility/debug entrypoint for the older create-only bridge.

Usage:
  ./.venv/bin/python scripts/openclaw_create_event_bridge.py "내일 오후 5시에 윤하 테니스 넣어줘"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from openclaw_molly_bridge import run_create_event_bridge


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/openclaw_create_event_bridge.py '<message>'")

    message_text = " ".join(sys.argv[1:]).strip()
    result = run_create_event_bridge(message_text)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
