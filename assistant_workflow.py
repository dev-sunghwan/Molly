"""
assistant_workflow.py — Minimal assistant workflow for Gmail-driven candidates.

Phase 5 connects Gmail messages to Molly's shared intent and workflow status.
The implementation is intentionally hybrid:
- use a structured extraction draft when one is available
- fall back to deterministic heuristics otherwise
- keep final validation and execution in Python
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

import config
import gmail_adapter
import utils
from email_extraction import ExtractedEventDraft
from gmail_adapter import GmailMessage
from intent_models import IntentAction, IntentResolution, IntentSource, ResolutionStatus, ScheduleIntent


class CandidateStatus(str):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    IGNORED = "ignored"


@dataclass
class EmailCandidate:
    status: str
    message_id: str
    reason: str
    intent: ScheduleIntent | None = None
    missing_fields: list[str] = field(default_factory=list)
    summary: str | None = None


def build_candidate_from_email(
    message: GmailMessage,
    extracted_draft: ExtractedEventDraft | None = None,
) -> EmailCandidate:
    sender_email = gmail_adapter.extract_sender_email(message.sender)
    if config.GMAIL_ALLOWED_SENDERS and sender_email not in config.GMAIL_ALLOWED_SENDERS:
        return EmailCandidate(
            status=CandidateStatus.IGNORED,
            message_id=message.message_id,
            reason="Sender is not in Molly's Gmail allowlist.",
            summary=message.subject or message.snippet,
        )

    if extracted_draft is not None:
        candidate = _build_candidate_from_extracted_draft(message, extracted_draft)
        if candidate is not None:
            return candidate

    text = _combined_text(message)
    lower = text.lower()

    if not _looks_schedule_related(lower):
        return EmailCandidate(
            status=CandidateStatus.IGNORED,
            message_id=message.message_id,
            reason="Message does not look scheduling-related.",
            summary=message.subject or message.snippet,
        )

    calendar = _extract_calendar(text, sender_email)
    target_date = _extract_date(text)
    time_range = _extract_time_range(text)
    title = _derive_title(message)

    intent = ScheduleIntent(
        action=IntentAction.CREATE_EVENT,
        source=IntentSource.EMAIL,
        raw_input=text,
        target_calendar=calendar,
        title=title,
        target_date=target_date,
        time_range=time_range,
        metadata={
            "email_message_id": message.message_id,
            "email_subject": message.subject,
            "email_sender": message.sender,
            "email_sender_normalized": sender_email,
            "all_day": time_range is None,
        },
    )

    missing: list[str] = []
    if calendar is None:
        missing.append("target_calendar")
    if target_date is None:
        missing.append("target_date")

    if missing:
        return EmailCandidate(
            status=CandidateStatus.NEEDS_CLARIFICATION,
            message_id=message.message_id,
            reason="Email requires clarification before Molly can execute it.",
            intent=intent,
            missing_fields=missing,
            summary=_candidate_summary(intent),
        )

    return EmailCandidate(
        status=CandidateStatus.READY,
        message_id=message.message_id,
        reason="Email contains enough scheduling information for a candidate.",
        intent=intent,
        summary=_candidate_summary(intent),
    )


def _build_candidate_from_extracted_draft(
    message: GmailMessage,
    draft: ExtractedEventDraft,
) -> EmailCandidate | None:
    sender_email = gmail_adapter.extract_sender_email(message.sender)

    if not draft.is_schedule_related:
        return EmailCandidate(
            status=CandidateStatus.IGNORED,
            message_id=message.message_id,
            reason=draft.reasoning or "LLM extraction marked this message as not scheduling-related.",
            summary=message.subject or message.snippet,
        )

    target_date = _parse_date_text(draft.target_date_text)
    time_range = _parse_time_text(draft.time_text)
    title = draft.title or _derive_title(message)

    intent = ScheduleIntent(
        action=IntentAction.CREATE_EVENT,
        source=IntentSource.EMAIL,
        raw_input=_combined_text(message),
        target_calendar=draft.target_calendar,
        title=title,
        target_date=target_date,
        time_range=time_range,
        metadata={
            "email_message_id": message.message_id,
            "email_subject": message.subject,
            "email_sender": message.sender,
            "email_sender_normalized": sender_email,
            "all_day": time_range is None,
            "llm_confidence": draft.confidence,
            "llm_reasoning": draft.reasoning,
            "location": draft.location,
        },
    )

    missing = list(draft.missing_fields)
    if draft.target_calendar is None and "target_calendar" not in missing:
        missing.append("target_calendar")
    if target_date is None and "target_date" not in missing:
        missing.append("target_date")

    if missing:
        return EmailCandidate(
            status=CandidateStatus.NEEDS_CLARIFICATION,
            message_id=message.message_id,
            reason=draft.reasoning or "LLM extraction still requires clarification.",
            intent=intent,
            missing_fields=missing,
            summary=_candidate_summary(intent),
        )

    return EmailCandidate(
        status=CandidateStatus.READY,
        message_id=message.message_id,
        reason=draft.reasoning or "LLM extraction produced a complete scheduling candidate.",
        intent=intent,
        summary=_candidate_summary(intent),
    )


def build_intent_resolution(candidate: EmailCandidate) -> IntentResolution | None:
    if candidate.intent is None:
        return None
    if candidate.status == CandidateStatus.READY:
        return IntentResolution(status=ResolutionStatus.READY, intent=candidate.intent)
    if candidate.status == CandidateStatus.NEEDS_CLARIFICATION:
        return IntentResolution(
            status=ResolutionStatus.NEEDS_CLARIFICATION,
            intent=candidate.intent,
            missing_fields=list(candidate.missing_fields),
            clarification_prompt=_clarification_prompt(candidate.missing_fields),
            reason=candidate.reason,
        )
    return None


def _combined_text(message: GmailMessage) -> str:
    parts = [message.subject, message.snippet, _clean_body_text(message.body_text)]
    return "\n".join(part for part in parts if part).strip()


def _looks_schedule_related(lower_text: str) -> bool:
    keywords = [
        "today",
        "tomorrow",
        "mon",
        "tue",
        "wed",
        "thu",
        "fri",
        "sat",
        "sun",
        ":",
        "meeting",
        "appointment",
        "dentist",
        "concert",
        "lesson",
        "game",
        "practice",
        "school",
        "schedule",
    ]
    return any(keyword in lower_text for keyword in keywords)


def _extract_calendar(text: str, sender_email: str | None) -> str | None:
    lower_text = text.lower()
    alias_map = {
        "sunghwan": ["sunghwan", "성환", "sung hwan"],
        "jeeyoung": ["jeeyoung", "지영", "jiyoung", "ji young"],
        "younha": ["younha", "윤하", "youn ha"],
        "haneul": ["haneul", "하늘", "eleanor"],
        "younho": ["younho", "윤호", "youn ho"],
        "family": ["family", "가족"],
    }
    best_calendar = None
    best_score = 0
    for calendar, aliases in alias_map.items():
        score = sum(lower_text.count(alias.lower()) for alias in aliases)
        if score > best_score:
            best_score = score
            best_calendar = calendar
    if best_calendar:
        return best_calendar

    sender_map = {
        "ray.sunghwan@gmail.com": "sunghwan",
        "sunghwan.k@hanwha.com": "sunghwan",
        "jylim3287@gmail.com": "jeeyoung",
    }
    return sender_map.get((sender_email or "").lower())


def _extract_date(text: str):
    lower_text = text.lower()
    for match in re.finditer(
        r"\b(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
        r"(?:\s+\d{4})?|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}"
        r"(?:st|nd|rd|th)?(?:,\s*\d{4})?)\b",
        lower_text,
    ):
        parsed = utils.parse_date(match.group(0))
        if parsed is not None:
            return parsed
    tokens = lower_text.replace(",", " ").replace("\n", " ").split()
    for token in tokens:
        parsed = utils.parse_date(token)
        if parsed is not None:
            return parsed
    return None


def _parse_date_text(date_text: str | None):
    if not date_text:
        return None
    tokens = date_text.lower().replace(",", " ").split()
    joined = " ".join(tokens)
    direct = utils.parse_date(joined)
    if direct is not None:
        return direct
    for token in tokens:
        parsed = utils.parse_date(token)
        if parsed is not None:
            return parsed
    return None


def _extract_time_range(text: str):
    normalized = text.replace("–", "-").replace("—", "-")
    range_match = re.search(
        r"\b\d{1,2}(?::|\.)?\d{0,2}\s*(?:am|pm)?\s*-\s*\d{1,2}(?:(?::|\.)\d{2})?\s*(?:am|pm)?(?:\s*(?:bst|gmt|utc))?\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if range_match:
        parsed = utils.parse_time(range_match.group(0))
        if parsed is not None:
            from intent_models import TimeRange

            return TimeRange(start=parsed[0], end=parsed[1])

    tokens = text.replace("\n", " ").split()
    for token in tokens:
        parsed = utils.parse_time(token.strip(".,"))
        if parsed is not None:
            from intent_models import TimeRange

            return TimeRange(start=parsed[0], end=parsed[1])
    return None


def _parse_time_text(time_text: str | None):
    if not time_text:
        return None
    parsed = utils.parse_time(time_text.strip())
    if parsed is None:
        return None
    from intent_models import TimeRange

    return TimeRange(start=parsed[0], end=parsed[1])


def _derive_title(message: GmailMessage) -> str:
    if message.subject:
        return message.subject.strip()
    if message.snippet:
        return message.snippet.strip()
    return "(email event)"


def _candidate_summary(intent: ScheduleIntent) -> str:
    parts = [intent.title or "(no title)"]
    if intent.target_calendar:
        parts.append(f"calendar={intent.target_calendar}")
    if intent.target_date:
        parts.append(f"date={intent.target_date.isoformat()}")
    if intent.time_range:
        parts.append(f"time={intent.time_range.start}-{intent.time_range.end}")
    return " | ".join(parts)


def _clean_body_text(body_text: str) -> str:
    if not body_text:
        return ""

    lines: list[str] = []
    for raw_line in body_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if line.startswith("---------- Forwarded message"):
            continue
        if re.match(r"^(from|sent|date|to|subject|cc|bcc):", lower):
            continue
        if lower.startswith("[aws") or lower.startswith("[cid:"):
            continue
        if "http://" in lower or "https://" in lower:
            continue
        lines.append(line)
    return "\n".join(lines)


def _clarification_prompt(missing_fields: list[str]) -> str:
    if missing_fields == ["target_calendar"]:
        return "This email looks like a schedule item, but Molly needs to know which family calendar to use."
    if missing_fields == ["target_date"]:
        return "This email looks scheduling-related, but Molly could not determine the date."
    if "target_calendar" in missing_fields and "target_date" in missing_fields:
        return (
            "This email looks like a schedule item, but Molly needs both the target family calendar "
            "and the date before it can continue."
        )
    return "Molly needs more information before it can use this email."
