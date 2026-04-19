"""
spouse_notifications.py — Notify one spouse when the other records a schedule change.
"""
from __future__ import annotations

import asyncio

from telegram import Bot

import config
from intent_models import IntentAction
import utils


_SPOUSE_NAME_PAIRS = {
    "sunghwan": "jeeyoung",
    "jeeyoung": "sunghwan",
}

_NAME_ALIASES = {
    "sunghwan": "sunghwan",
    "sung hwan": "sunghwan",
    "sung-hwan": "sunghwan",
    "성환": "sunghwan",
    "dev sunghwan": "sunghwan",
    "jeeyoung": "jeeyoung",
    "jee young": "jeeyoung",
    "jee-young": "jeeyoung",
    "지영": "jeeyoung",
}


def spouse_notification_target(
    actor_user_id: int | None,
    actor_name: str | None = None,
) -> int | None:
    actor_key = _actor_key(actor_user_id=actor_user_id, actor_name=actor_name)
    if actor_key is None:
        return None
    partner_name = _SPOUSE_NAME_PAIRS.get(actor_key)
    if partner_name is None:
        return None
    return config.USER_IDS_BY_NAME.get(partner_name)


def build_spouse_notification(
    actor_user_id: int | None,
    intent,
    success: bool,
    actor_name: str | None = None,
) -> str | None:
    if not success:
        return None

    target_user_id = spouse_notification_target(actor_user_id, actor_name=actor_name)
    if target_user_id is None:
        return None

    if intent.action not in {
        IntentAction.CREATE_EVENT,
        IntentAction.UPDATE_EVENT,
        IntentAction.DELETE_EVENT,
        IntentAction.DELETE_SERIES,
    }:
        return None

    actor_label = _actor_display_name(actor_user_id, actor_name=actor_name)
    calendar_label = _calendar_label(intent.target_calendar)
    schedule_summary = _schedule_summary(intent)

    if intent.action == IntentAction.CREATE_EVENT:
        return f"{actor_label}이 [{calendar_label}] {schedule_summary} 일정을 추가했어요."
    if intent.action == IntentAction.UPDATE_EVENT:
        return f"{actor_label}이 [{calendar_label}] {schedule_summary} 일정을 수정했어요."
    if intent.action == IntentAction.DELETE_EVENT:
        return f"{actor_label}이 [{calendar_label}] {schedule_summary} 일정을 삭제했어요."
    if intent.action == IntentAction.DELETE_SERIES:
        return f"{actor_label}이 [{calendar_label}] {intent.title or '(no title)'} 반복 일정을 삭제했어요."
    return None


async def notify_spouse_via_bot(
    bot,
    actor_user_id: int | None,
    intent,
    success: bool,
    actor_name: str | None = None,
) -> bool:
    target_user_id = spouse_notification_target(actor_user_id, actor_name=actor_name)
    text = build_spouse_notification(actor_user_id, intent, success, actor_name=actor_name)
    if target_user_id is None or text is None:
        return False
    await bot.send_message(chat_id=target_user_id, text=text)
    return True


def notify_spouse_sync(
    actor_user_id: int | None,
    intent,
    success: bool,
    actor_name: str | None = None,
) -> bool:
    target_user_id = spouse_notification_target(actor_user_id, actor_name=actor_name)
    text = build_spouse_notification(actor_user_id, intent, success, actor_name=actor_name)
    if target_user_id is None or text is None:
        return False

    async def _send() -> None:
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=target_user_id, text=text)

    asyncio.run(_send())
    return True



def _actor_key(actor_user_id: int | None, actor_name: str | None = None) -> str | None:
    if actor_user_id is not None:
        actor = config.USERS.get(actor_user_id)
        if actor is not None:
            return actor["name"].strip().lower()
    if not actor_name:
        return None
    normalized = " ".join(actor_name.strip().lower().replace("_", " ").replace(".", " ").split())
    if normalized in _NAME_ALIASES:
        return _NAME_ALIASES[normalized]
    if normalized in config.USER_IDS_BY_NAME:
        return normalized
    return None



def _actor_display_name(actor_user_id: int | None, actor_name: str | None = None) -> str:
    actor_key = _actor_key(actor_user_id=actor_user_id, actor_name=actor_name)
    if actor_key is None:
        return "누군가"
    return _calendar_label(actor_key)



def _calendar_label(value: str | None) -> str:
    if not value:
        return "캘린더"
    normalized = value.strip().lower()
    event = {"_calendar_name": normalized}
    label = utils.format_calendar_label(event)
    return label or value



def _schedule_summary(intent) -> str:
    title = intent.title or "(no title)"
    if intent.action == IntentAction.DELETE_SERIES:
        return title

    if intent.date_range is not None and intent.time_range is not None:
        return (
            f"{title} ({utils.format_short_day_date(intent.target_date)} {intent.time_range.start} – "
            f"{utils.format_short_day_date(intent.date_range.end)} {intent.time_range.end})"
        )

    if intent.target_date and intent.time_range:
        return (
            f"{title} ({utils.format_short_day_date(intent.target_date)} "
            f"{intent.time_range.start}–{intent.time_range.end})"
        )

    if intent.target_date:
        return f"{title} ({utils.format_short_day_date(intent.target_date)})"

    return title
