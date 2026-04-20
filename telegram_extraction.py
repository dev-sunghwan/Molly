"""
telegram_extraction.py — Structured Telegram extraction models and helpers.

This module defines the contract for an LLM/OpenClaw-assisted Telegram
interpretation layer. The extractor is expected to produce structured fields;
deterministic Python still validates and executes the final result.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExtractedTelegramDraft:
    action: str | None = None
    target_calendar: str | None = None
    title: str | None = None
    target_date_text: str | None = None
    time_text: str | None = None
    limit: int | None = None
    confidence: float | None = None
    reasoning: str | None = None
    missing_fields: list[str] = field(default_factory=list)


def build_extraction_prompt(message_text: str) -> str:
    """
    Build a compact prompt that a future LLM/OpenClaw layer can use to return
    structured Telegram scheduling extraction.
    """
    return (
        "Read the Telegram message and return a structured scheduling draft.\n"
        "Choose one action from: create_event, view_daily, view_range.\n"
        "If create_event, extract title, family member/calendar, date text, "
        "time text, and any missing fields.\n"
        "If view_daily or view_range, extract the relevant date/range intent.\n"
        "Do not guess a calendar when the user did not name one explicitly.\n"
        "For requests like 'upcoming' or 'next' without a calendar, leave target_calendar empty so Molly Core can use its all-calendars default.\n"
        "Do not execute anything.\n\n"
        f"Telegram message:\n{message_text}\n"
    )
