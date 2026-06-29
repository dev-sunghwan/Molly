"""
Helpers for journaling Telegram reply delivery and recovering missing replies.
"""
from __future__ import annotations

import asyncio
from telegram import Bot

import config
import state_store


async def send_and_track_reply(
    *,
    request_id: str,
    chat_id: int,
    message: str,
    bot: Bot | None = None,
) -> dict:
    telegram_bot = bot or Bot(token=config.TELEGRAM_BOT_TOKEN)
    try:
        await telegram_bot.send_message(chat_id=chat_id, text=message)
    except Exception as exc:
        return state_store.update_command_reply_status(
            request_id,
            "send_failed",
            reply_error=f"{type(exc).__name__}: {exc}",
        )
    return state_store.update_command_reply_status(request_id, "sent", reply_error=None)


def recover_missing_replies(*, limit: int = 20, bot: Bot | None = None) -> dict:
    state_store.init_db()
    candidates = list_missing_reply_commands(limit=limit)
    resent: list[str] = []
    failed: list[dict] = []
    for row in candidates:
        request_id = str(row["request_id"])
        execution_result = row.get("execution_result") or {}
        message = str(execution_result.get("message") or "").strip()
        chat_id = telegram_chat_id(row)
        if not message or chat_id is None:
            state_store.update_command_reply_status(
                request_id,
                "recovery_skipped",
                reply_error="Missing message or Telegram chat id for recovery.",
            )
            failed.append({"request_id": request_id, "reason": "missing message/chat_id"})
            continue
        try:
            asyncio.run(send_and_track_reply(request_id=request_id, chat_id=chat_id, message=message, bot=bot))
        except Exception as exc:
            failed.append({"request_id": request_id, "reason": f"{type(exc).__name__}: {exc}"})
            continue
        updated = state_store.get_command_by_request_id(request_id)
        if updated and updated.get("reply_status") == "sent":
            resent.append(request_id)
        else:
            failed.append({"request_id": request_id, "reason": updated.get("reply_status") if updated else "unknown"})
    return {
        "success": True,
        "action": "recover_missing_replies",
        "checked": len(candidates),
        "resent": resent,
        "failed": failed,
    }


def list_missing_reply_commands(*, limit: int = 20) -> list[dict]:
    rows = state_store.list_commands(status="executed", source="telegram", limit=max(limit * 5, limit))
    missing = [row for row in rows if row.get("reply_status") in (None, "")]
    return missing[:limit]


def telegram_chat_id(row: dict) -> int | None:
    for value in (row.get("source_channel_id"), row.get("request_id")):
        chat_id = _telegram_chat_id_from_text(value)
        if chat_id is not None:
            return chat_id
    return None


def _telegram_chat_id_from_text(value: object) -> int | None:
    if value is None:
        return None
    parts = [part for part in str(value).split(":") if part]
    for index, part in enumerate(parts):
        if part == "telegram" and index + 1 < len(parts):
            candidate = parts[index + 1]
            if candidate.lstrip("-").isdigit():
                return int(candidate)
    return None
