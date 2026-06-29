"""
Molly admin diagnostics for Slack/OpenClaw development use.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from telegram import Bot

import config
import state_store
from scripts import molly_reply_tracker

_SENSITIVE_KEY_PARTS = (
    "authorization",
    "api_key",
    "apikey",
    "bot_token",
    "bottoken",
    "client_secret",
    "credential",
    "password",
    "secret",
    "token",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Molly admin diagnostics.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    summary_parser = subparsers.add_parser("summary", help="Show command and sync counts")
    summary_parser.add_argument("--source", help="Filter command counts by source")

    commands_parser = subparsers.add_parser("commands", help="List recent command journal rows")
    commands_parser.add_argument("--status")
    commands_parser.add_argument("--source")
    commands_parser.add_argument("--limit", type=int, default=20)
    commands_parser.add_argument("--include-text", action="store_true")
    commands_parser.add_argument("--include-payload", action="store_true")

    command_parser = subparsers.add_parser("command", help="Show one command journal row")
    command_parser.add_argument("--request-id", required=True)
    command_parser.add_argument("--include-text", action="store_true")
    command_parser.add_argument("--include-payload", action="store_true")

    sync_parser = subparsers.add_parser("sync", help="List Google sync outbox rows")
    sync_parser.add_argument("--status")
    sync_parser.add_argument("--limit", type=int, default=20)
    sync_parser.add_argument("--include-payload", action="store_true")

    resend_parser = subparsers.add_parser("resend", help="Resend a stored execution result")
    resend_parser.add_argument("--request-id", required=True)
    recover_parser = subparsers.add_parser("recover-replies", help="Recover executed telegram commands with missing reply status")
    recover_parser.add_argument("--limit", type=int, default=20)

    resend_parser.add_argument(
        "--force",
        action="store_true",
        help="Allow resend for non-telegram sources or failed execution rows.",
    )

    args = parser.parse_args()
    state_store.init_db()

    if args.subcommand == "summary":
        result = {
            "success": True,
            "action": "admin_summary",
            "commands_by_status": state_store.count_commands_by_status(source=args.source),
            "google_sync_by_status": state_store.count_google_sync_outbox_by_status(),
        }
    elif args.subcommand == "commands":
        result = {
            "success": True,
            "action": "admin_commands",
            "commands": [
                _command_summary(
                    row,
                    include_text=args.include_text,
                    include_payload=args.include_payload,
                )
                for row in state_store.list_commands(
                    status=args.status,
                    source=args.source,
                    limit=args.limit,
                )
            ],
        }
    elif args.subcommand == "command":
        row = state_store.get_command_by_request_id(args.request_id)
        result = {
            "success": row is not None,
            "action": "admin_command",
            "command": _command_summary(
                row,
                include_text=args.include_text,
                include_payload=args.include_payload,
            )
            if row
            else None,
        }
    elif args.subcommand == "sync":
        result = {
            "success": True,
            "action": "admin_sync",
            "outbox": [
                _sync_summary(row, include_payload=args.include_payload)
                for row in state_store.list_google_sync_outbox(
                    status=args.status,
                    limit=args.limit,
                )
            ],
        }
    elif args.subcommand == "resend":
        result = _resend_command(args.request_id, force=args.force)
    elif args.subcommand == "recover-replies":
        result = molly_reply_tracker.recover_missing_replies(limit=args.limit)
    else:
        raise SystemExit(f"Unsupported subcommand: {args.subcommand}")

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


def _command_summary(
    row: dict,
    *,
    include_text: bool = False,
    include_payload: bool = False,
) -> dict:
    result = {
        "id": row["id"],
        "request_id": row["request_id"],
        "source": row["source"],
        "source_message_id": row["source_message_id"],
        "source_channel_id": row["source_channel_id"],
        "status": row["status"],
        "parser_version": row["parser_version"],
        "action": _command_action(row),
        "success": _execution_success(row),
        "validation_error": _preview(row["validation_error"]),
        "execution_error": _execution_error(row),
        "reply_status": row["reply_status"],
        "reply_error": _preview(row["reply_error"]),
        "reply_attempts": row["reply_attempts"],
        "last_reply_at": row["last_reply_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_text:
        result["raw_text"] = _preview(row["raw_text"], limit=240)
    if include_payload:
        result["raw_payload"] = _redact(row["raw_payload"])
        result["structured_payload"] = _redact(row["structured_payload"])
        result["execution_result"] = _redact(row["execution_result"])
    return result


def _sync_summary(row: dict, *, include_payload: bool = False) -> dict:
    result = {
        "id": row["id"],
        "operation": row["operation"],
        "local_event_id": row["local_event_id"],
        "status": row["status"],
        "attempts": row["attempts"],
        "last_error": _preview(row["last_error"]),
        "google_calendar_id": row["google_calendar_id"],
        "google_event_id": row["google_event_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_payload:
        result["payload"] = _redact(row["payload"])
    return result


def _resend_command(request_id: str, *, force: bool = False) -> dict:
    row = state_store.get_command_by_request_id(request_id)
    if row is None:
        return {
            "success": False,
            "action": "admin_resend",
            "message": f"Command not found: {request_id}",
        }
    if row["source"] != "telegram" and not force:
        return _resend_rejected(
            row,
            "Refusing to resend non-telegram command without --force.",
        )
    execution_result = row.get("execution_result")
    if not isinstance(execution_result, dict):
        return _resend_rejected(row, "Command has no stored execution result.")
    if execution_result.get("success") is not True and not force:
        return _resend_rejected(
            row,
            "Refusing to resend failed execution result without --force.",
        )
    message = str(execution_result.get("message") or "").strip()
    if not message:
        return _resend_rejected(row, "Stored execution result has no message.")
    chat_id = _telegram_chat_id(row)
    if chat_id is None:
        return _resend_rejected(row, "Command has no usable Telegram chat id.")

    try:
        asyncio.run(_send_telegram_message(chat_id, message))
    except Exception as exc:
        updated = state_store.update_command_reply_status(
            request_id,
            "resend_failed",
            reply_error=f"{type(exc).__name__}: {exc}",
        )
        return {
            "success": False,
            "action": "admin_resend",
            "request_id": request_id,
            "reply_status": updated["reply_status"],
            "reply_attempts": updated["reply_attempts"],
            "message": f"Resend failed: {type(exc).__name__}: {exc}",
        }

    updated = state_store.update_command_reply_status(request_id, "resent", reply_error=None)
    return {
        "success": True,
        "action": "admin_resend",
        "request_id": request_id,
        "chat_id": str(chat_id),
        "reply_status": updated["reply_status"],
        "reply_attempts": updated["reply_attempts"],
        "message": "Resent stored execution result.",
    }


def _resend_rejected(row: dict, reason: str) -> dict:
    return {
        "success": False,
        "action": "admin_resend",
        "request_id": row["request_id"],
        "reply_status": row["reply_status"],
        "reply_attempts": row["reply_attempts"],
        "message": reason,
    }


async def _send_telegram_message(chat_id: int, message: str) -> None:
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    await bot.send_message(chat_id=chat_id, text=message)


def _telegram_chat_id(row: dict) -> int | None:
    return molly_reply_tracker.telegram_chat_id(row)


def _command_action(row: dict) -> str | None:
    structured = row.get("structured_payload") or {}
    raw = row.get("raw_payload") or {}
    return structured.get("action") or raw.get("action") or raw.get("subcommand")


def _execution_success(row: dict) -> bool | None:
    execution_result = row.get("execution_result")
    if not isinstance(execution_result, dict) or "success" not in execution_result:
        return None
    return bool(execution_result["success"])


def _execution_error(row: dict) -> str | None:
    execution_result = row.get("execution_result")
    if not isinstance(execution_result, dict):
        return None
    error = execution_result.get("error")
    if error is None and execution_result.get("success") is False:
        error = execution_result.get("message")
    return _preview(error)


def _preview(value: object, *, limit: int = 160) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _redact(value):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_sensitive_key(key) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).replace("-", "_").lower()
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


if __name__ == "__main__":
    main()
