"""
Execute a structured Molly Core request once.

Usage:
  echo '{"action":"create_event",...}' | ./.venv/bin/python scripts/molly_core_execute.py
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
import state_store
from calendar_repository import CalendarRepository
from molly_core import MollyCore
from molly_core_requests import resolution_from_request

_MUTATING_ACTIONS = {
    "create_event",
    "update_event",
    "delete_event",
    "move_event",
    "delete_series",
}


def _journal_enabled() -> bool:
    return os.getenv("MOLLY_COMMAND_JOURNAL_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _record_request(payload: dict) -> str | None:
    if not _journal_enabled():
        return None
    request_id = str(payload.get("request_id") or f"molly-core-{uuid.uuid4()}")
    source = str(payload.get("source") or payload.get("request_source") or "structured_cli")
    try:
        state_store.record_inbound_command(
            request_id=request_id,
            source=source,
            raw_text=str(payload.get("raw_input") or ""),
            raw_payload=payload,
            source_message_id=_optional_string(payload.get("source_message_id")),
            source_user_id=_optional_string(payload.get("source_user_id")),
            source_user_name=_optional_string(payload.get("source_user_name")),
            source_channel_id=_optional_string(payload.get("source_channel_id")),
        )
        return request_id
    except Exception as exc:
        print(
            f"[molly_core_execute] command journal write failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None


def _update_request(
    request_id: str | None,
    status: str,
    result: dict | None = None,
    *,
    structured_payload: dict | None = None,
    validation_error: str | None = None,
) -> None:
    if request_id is None or not _journal_enabled():
        return
    try:
        state_store.update_command_status(
            request_id,
            status,
            structured_payload=structured_payload,
            validation_error=validation_error,
            execution_result=result,
        )
    except Exception as exc:
        print(
            f"[molly_core_execute] command journal update failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )


def _completed_result_for_request(request_id: str | None) -> dict | None:
    if request_id is None or not _journal_enabled():
        return None
    stored = state_store.get_command_by_request_id(request_id)
    if stored is None:
        return None
    if stored["status"] != "executed":
        return None
    result = stored.get("execution_result")
    return result if isinstance(result, dict) else None


def _enforce_request_id_policy(explicit_request_id: str | None, payload: dict) -> None:
    if not config.REQUIRE_REQUEST_ID_FOR_MUTATIONS:
        return
    action = str(payload.get("action") or "")
    if action not in _MUTATING_ACTIONS:
        return
    if explicit_request_id:
        return
    raise ValueError(
        "Stable request_id is required for mutating Molly requests when "
        "MOLLY_REQUIRE_REQUEST_ID_FOR_MUTATIONS=1"
    )


def _optional_string(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def main() -> None:
    payload = json.load(sys.stdin)
    explicit_request_id = _optional_string(payload.get("request_id"))

    state_store.init_db()
    request_id = _record_request(payload)
    completed_result = _completed_result_for_request(request_id)
    if completed_result is not None:
        print(json.dumps(completed_result, ensure_ascii=False))
        return

    try:
        _enforce_request_id_policy(explicit_request_id, payload)
        _update_request(request_id, "parsing")
        resolution = resolution_from_request(payload)
        _update_request(request_id, "validated", structured_payload=payload)
        config.validate()
        calendar_repo = CalendarRepository.from_config()
        core = MollyCore(calendar_repo)
        _update_request(request_id, "executing")
        message = core.execute_resolution(resolution)
        result = {
            "success": not message.startswith("❌"),
            "action": resolution.intent.action.value,
            "message": message,
        }
    except ValueError as exc:
        _update_request(
            request_id,
            "rejected",
            {"success": False, "error": f"{type(exc).__name__}: {exc}"},
            validation_error=str(exc),
        )
        raise
    except SystemExit as exc:
        _update_request(
            request_id,
            "failed",
            {"success": False, "error": f"SystemExit: {exc}"},
        )
        raise
    except Exception as exc:
        _update_request(
            request_id,
            "failed",
            {"success": False, "error": f"{type(exc).__name__}: {exc}"},
        )
        raise

    _update_request(request_id, "executed" if result["success"] else "failed", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
