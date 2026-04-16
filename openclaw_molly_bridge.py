"""
openclaw_molly_bridge.py — Bridge OpenClaw extraction to Molly Core execution.

This module provides the first narrow OpenClaw-centered bridge for one end-to-
end action: create_event. It is intentionally split into two stages:

1. Ask OpenClaw for a structured create_event request in JSON.
2. Hand that JSON to Molly Core's deterministic CLI executor.

The OpenClaw invocation is kept behind a small adapter so the exact CLI flags
can be finalized once the runtime surface is fully confirmed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent
MOLLY_CORE_EXECUTE = PROJECT_ROOT / "scripts" / "molly_core_execute.py"
MOLLY_CREATE_EVENT_EXEC = PROJECT_ROOT / "scripts" / "molly_create_event.py"
PROJECT_VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"


def build_create_event_prompt(message_text: str) -> str:
    return (
        "You are preparing a structured scheduling request for Molly Core.\n"
        "Return JSON only.\n"
        "The JSON must follow this schema:\n"
        "{\n"
        '  "action": "create_event",\n'
        '  "target_calendar": "sunghwan|jeeyoung|younha|haneul|younho|family",\n'
        '  "title": "string",\n'
        '  "target_date": "YYYY-MM-DD",\n'
        '  "start_time": "HH:MM",\n'
        '  "end_time": "HH:MM",\n'
        '  "all_day": false,\n'
        '  "raw_input": "original message",\n'
        '  "nlu": "openclaw",\n'
        '  "request_source": "openclaw_cli_bridge"\n'
        "}\n"
        "Only output a request when the schedule information is complete.\n"
        "If the request is incomplete or ambiguous, output:\n"
        '{ "status": "needs_clarification", "reason": "..." }\n\n'
        f"Telegram message:\n{message_text}\n"
    )


def run_create_event_bridge(
    message_text: str,
    *,
    infer_runner: Callable[[str], str] | None = None,
    execute_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    runner = infer_runner or infer_create_event_request_via_openclaw
    execute = execute_runner or execute_molly_core_request

    raw_output = runner(message_text)
    payload = _parse_json_output(raw_output)

    if payload.get("status") == "needs_clarification":
        return payload

    result = execute(payload)
    return {
        "status": "executed",
        "request": payload,
        "result": result,
    }


def infer_create_event_request_via_openclaw(message_text: str) -> str:
    prompt = build_create_event_prompt(message_text)
    command = _default_openclaw_command(prompt)
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    return completed.stdout.strip()


def execute_molly_core_request(payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(MOLLY_CORE_EXECUTE)],
        input=json.dumps(payload, ensure_ascii=False),
        check=True,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    return _parse_json_output(completed.stdout)


def build_exec_tool_command(payload: dict[str, Any]) -> list[str]:
    if payload.get("action") != "create_event":
        raise ValueError("Only create_event is supported by the exec tool command builder")

    return [
        str(_preferred_python_executable()),
        str(MOLLY_CREATE_EVENT_EXEC),
        "--calendar",
        str(payload["target_calendar"]),
        "--title",
        str(payload["title"]),
        "--date",
        str(payload["target_date"]),
        "--start",
        str(payload["start_time"]),
        "--end",
        str(payload["end_time"]),
        "--raw-input",
        str(payload.get("raw_input", "")),
        "--nlu",
        str(payload.get("nlu", "openclaw")),
        "--request-source",
        str(payload.get("request_source", "openclaw_exec_tool")),
    ]


def _preferred_python_executable() -> Path:
    if PROJECT_VENV_PYTHON.exists():
        return PROJECT_VENV_PYTHON
    return Path(sys.executable)


def _default_openclaw_command(prompt: str) -> list[str]:
    """
    Build the current best-guess OpenClaw CLI invocation.

    The exact CLI flags may still need one final adjustment once the runtime
    surface is fully verified. The bridge keeps this isolated in one place.
    """
    return [
        "openclaw",
        "infer",
        "model",
        "run",
        "--json",
        "--prompt",
        prompt,
    ]


def _parse_json_output(raw_output: str) -> dict[str, Any]:
    cleaned = _strip_code_fence(raw_output.strip())
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Bridge output must be a JSON object")
    return data


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
