"""
telegram_extractor_provider.py — Optional Telegram extraction provider hook.

This module provides a narrow integration point for a future OpenClaw/LLM
layer. Until a real provider is registered, Molly simply falls back to its
heuristic Telegram NLU.
"""
from __future__ import annotations

from collections.abc import Callable

from telegram_extraction import ExtractedTelegramDraft


TelegramExtractor = Callable[[str], ExtractedTelegramDraft | None]


def extract_draft(message_text: str, extractor: TelegramExtractor | None) -> ExtractedTelegramDraft | None:
    if extractor is None:
        return None
    return extractor(message_text)
