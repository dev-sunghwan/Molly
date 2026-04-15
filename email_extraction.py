"""
email_extraction.py — Structured email extraction models and helpers.

This module defines the contract for an LLM-assisted extraction layer.
The extractor is expected to produce structured fields; deterministic Python
still validates and executes the final result.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExtractedEventDraft:
    is_schedule_related: bool
    title: str | None = None
    target_calendar: str | None = None
    target_date_text: str | None = None
    time_text: str | None = None
    location: str | None = None
    confidence: float | None = None
    reasoning: str | None = None
    missing_fields: list[str] = field(default_factory=list)


def build_extraction_prompt(subject: str, sender: str, body_text: str) -> str:
    """
    Build a compact prompt that a future LLM/OpenClaw layer can use to return
    structured scheduling extraction.
    """
    return (
        "Read the email and return a structured scheduling draft.\n"
        "Decide whether the email is scheduling-related.\n"
        "If yes, extract title, family member/calendar, date text, time text, "
        "and any missing fields.\n"
        "Do not execute anything.\n\n"
        f"Subject: {subject}\n"
        f"Sender: {sender}\n"
        f"Body:\n{body_text}\n"
    )
