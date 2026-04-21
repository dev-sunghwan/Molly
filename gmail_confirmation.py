"""
gmail_confirmation.py — Gmail candidate confirmation flow for Molly.

This module turns stored inbox candidates into Telegram-facing confirmation
messages and deterministic execution steps.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from telegram import Bot

from calendar_repository import CalendarRepository
import config
from intent_models import DateRange, IntentAction, IntentResolution, IntentSource, ResolutionStatus, ScheduleIntent, TimeRange
from molly_core import MollyCore
import state_store


@dataclass
class NotificationResult:
    candidate_id: int
    sent_to: list[int]
    message: str


def pending_candidates(limit: int = 20) -> list[dict]:
    return state_store.list_email_candidates(
        decision_status="pending_confirmation",
        notified=False,
        limit=limit,
    )


def notify_pending_candidates(bot: Bot, limit: int = 20) -> list[NotificationResult]:
    notifications: list[NotificationResult] = []
    for candidate in pending_candidates(limit=limit):
        message = format_candidate_confirmation(candidate)
        sent_to: list[int] = []
        for user_id in config.ALLOWED_USER_IDS:
            bot.send_message(chat_id=user_id, text=message)
            sent_to.append(user_id)
        state_store.mark_email_candidate_notified(int(candidate["id"]))
        notifications.append(
            NotificationResult(
                candidate_id=int(candidate["id"]),
                sent_to=sent_to,
                message=message,
            )
        )
    return notifications


def list_candidate_summaries(decision_status: str | None = None, limit: int = 20) -> str:
    candidates = state_store.list_email_candidates(decision_status=decision_status, limit=limit)
    if not candidates:
        return "No Gmail candidates found."
    lines = [f"Gmail candidates: {len(candidates)}"]
    for candidate in candidates:
        lines.append(
            f"- #{candidate['id']} | {candidate['decision_status']} | "
            f"{candidate['summary'] or candidate['reason']}"
        )
    return "\n".join(lines)


def confirm_candidate(
    candidate_id: int,
    calendar_repo: CalendarRepository,
    actor_user_id: int | None = None,
) -> str:
    candidate = state_store.get_email_candidate(candidate_id)
    if candidate is None:
        return f"❌ Gmail candidate #{candidate_id} was not found."
    if candidate["decision_status"] == "ignored":
        return f"❌ Gmail candidate #{candidate_id} was already ignored."
    if candidate["decision_status"] == "executed":
        return f"❌ Gmail candidate #{candidate_id} was already executed."

    intent = _candidate_intent(candidate)
    if intent is None:
        return f"❌ Gmail candidate #{candidate_id} cannot be executed because it has no resolved event."

    core = MollyCore(calendar_repo)
    resolution = IntentResolution(status=ResolutionStatus.READY, intent=intent)
    message = core.execute_resolution(resolution, user_id=actor_user_id)
    state_store.update_email_candidate_decision(
        candidate_id,
        "executed",
        metadata_updates={
            "confirmed_by_user_id": actor_user_id,
            "execution_message": message,
        },
    )
    return f"Gmail candidate #{candidate_id}\n{message}"


def ignore_candidate(candidate_id: int, actor_user_id: int | None = None) -> str:
    candidate = state_store.get_email_candidate(candidate_id)
    if candidate is None:
        return f"❌ Gmail candidate #{candidate_id} was not found."
    if candidate["decision_status"] == "executed":
        return f"❌ Gmail candidate #{candidate_id} was already executed."
    state_store.update_email_candidate_decision(
        candidate_id,
        "ignored",
        metadata_updates={"ignored_by_user_id": actor_user_id},
    )
    return f"Ignored Gmail candidate #{candidate_id}: {candidate['summary'] or candidate['reason']}"


def format_candidate_confirmation(candidate: dict) -> str:
    summary = candidate["summary"] or candidate["reason"]
    metadata = candidate["metadata"]
    subject = metadata.get("subject") or "(no subject)"
    sender = metadata.get("sender") or "(unknown sender)"
    return (
        f"📬 Gmail candidate #{candidate['id']}\n"
        f"Subject: {subject}\n"
        f"From: {sender}\n"
        f"{summary}\n\n"
        f"Reply with:\n"
        f"gmail confirm {candidate['id']}\n"
        f"or\n"
        f"gmail ignore {candidate['id']}"
    )


def _candidate_intent(candidate: dict) -> ScheduleIntent | None:
    payload = candidate["candidate"].get("intent")
    if payload is None:
        return None
    target_date = date.fromisoformat(payload["target_date"]) if payload.get("target_date") else None
    date_range = payload.get("date_range")
    time_range = payload.get("time_range")
    return ScheduleIntent(
        action=IntentAction(payload["action"]),
        source=IntentSource(payload["source"]),
        raw_input=payload.get("raw_input", ""),
        target_calendar=payload.get("target_calendar"),
        title=payload.get("title"),
        target_date=target_date,
        date_range=(
            DateRange(
                start=date.fromisoformat(date_range["start"]),
                end=date.fromisoformat(date_range["end"]),
            )
            if date_range
            else None
        ),
        time_range=(
            TimeRange(start=time_range["start"], end=time_range["end"])
            if time_range
            else None
        ),
        recurrence=list(payload.get("recurrence", [])),
        search_query=payload.get("search_query"),
        help_topic=payload.get("help_topic"),
        limit=payload.get("limit"),
        changes=dict(payload.get("changes", {})),
        metadata=dict(payload.get("metadata", {})),
    )
