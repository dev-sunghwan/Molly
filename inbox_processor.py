"""
inbox_processor.py — One-shot inbox processing loop for Molly.

Phase 6 processes recent inbox messages conservatively:
- fetch recent Gmail messages
- skip messages already recorded in processed_inputs
- build assistant workflow candidates for new messages
- record candidate status in SQLite
- return a compact processing summary
"""
from __future__ import annotations

from dataclasses import dataclass

import assistant_workflow
import gmail_adapter
import state_store
from assistant_workflow import EmailCandidate


@dataclass
class ProcessedMessage:
    message_id: str
    status: str
    subject: str
    summary: str
    candidate_id: int | None = None
    skipped: bool = False


def process_recent_inbox_messages(
    service,
    max_results: int = 10,
    query: str = "in:inbox",
) -> list[ProcessedMessage]:
    state_store.init_db()
    processed: list[ProcessedMessage] = []

    message_ids = gmail_adapter.list_message_ids(service, max_results=max_results, query=query)
    for message_id in message_ids:
        if state_store.is_processed_input("gmail", message_id):
            stored = state_store.get_processed_input("gmail", message_id)
            processed.append(
                ProcessedMessage(
                    message_id=message_id,
                    status=stored["status"],
                    subject=stored["metadata"].get("subject", ""),
                    summary=stored["metadata"].get("summary", "already processed"),
                    candidate_id=stored["metadata"].get("candidate_id"),
                    skipped=True,
                )
            )
            continue

        message = gmail_adapter.fetch_message(service, message_id)
        candidate = assistant_workflow.build_candidate_from_email(message)
        candidate_id = state_store.save_email_candidate(
            message_id=message.message_id,
            status=candidate.status,
            reason=candidate.reason,
            summary=candidate.summary,
            candidate_payload=_candidate_to_dict(candidate),
            metadata={
                "subject": message.subject,
                "sender": message.sender,
            },
        )
        state_store.mark_processed_input(
            source="gmail",
            external_id=message_id,
            status=candidate.status,
            metadata={
                "subject": message.subject,
                "sender": message.sender,
                "summary": candidate.summary or candidate.reason,
                "candidate_id": candidate_id,
            },
        )
        processed.append(
            ProcessedMessage(
                message_id=message_id,
                status=candidate.status,
                subject=message.subject,
                summary=candidate.summary or candidate.reason,
                candidate_id=candidate_id,
            )
        )

    return processed


def format_processing_report(processed_messages: list[ProcessedMessage]) -> str:
    if not processed_messages:
        return "No inbox messages were processed."

    lines = [f"Processed inbox messages: {len(processed_messages)}"]
    for item in processed_messages:
        prefix = "SKIP" if item.skipped else item.status.upper()
        subject = item.subject or "(no subject)"
        lines.append(f"- {prefix} | {subject} | {item.summary}")
    return "\n".join(lines)


def _candidate_to_dict(candidate: EmailCandidate) -> dict:
    payload = {
        "status": getattr(candidate, "status", ""),
        "message_id": getattr(candidate, "message_id", ""),
        "reason": getattr(candidate, "reason", ""),
        "summary": getattr(candidate, "summary", None),
        "missing_fields": list(getattr(candidate, "missing_fields", [])),
        "intent": None,
    }
    intent = getattr(candidate, "intent", None)
    if intent is not None:
        payload["intent"] = {
            "action": intent.action.value,
            "source": intent.source.value,
            "raw_input": intent.raw_input,
            "target_calendar": intent.target_calendar,
            "title": intent.title,
            "target_date": intent.target_date.isoformat() if intent.target_date else None,
            "date_range": (
                {
                    "start": intent.date_range.start.isoformat(),
                    "end": intent.date_range.end.isoformat(),
                }
                if intent.date_range is not None
                else None
            ),
            "time_range": (
                {
                    "start": intent.time_range.start,
                    "end": intent.time_range.end,
                }
                if intent.time_range is not None
                else None
            ),
            "recurrence": list(intent.recurrence),
            "search_query": intent.search_query,
            "help_topic": intent.help_topic,
            "limit": intent.limit,
            "changes": dict(intent.changes),
            "metadata": dict(intent.metadata),
        }
    return payload
