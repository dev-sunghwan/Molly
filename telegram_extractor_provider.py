"""
telegram_extractor_provider.py — Optional Telegram extraction provider hook.

This module chooses the configured Telegram extraction provider. Molly still
falls back to heuristic Telegram NLU when no provider is enabled or when the
provider returns no usable structured draft.
"""
from __future__ import annotations

from collections.abc import Callable

import config
import openclaw_telegram_provider
from telegram_extraction import ExtractedTelegramDraft


TelegramExtractor = Callable[[str], ExtractedTelegramDraft | None]


def build_extractor_from_config() -> TelegramExtractor | None:
    if config.TELEGRAM_EXTRACTOR_BACKEND == "openclaw":
        return openclaw_telegram_provider.build_extractor_from_config()
    return None


def extract_draft(message_text: str, extractor: TelegramExtractor | None) -> ExtractedTelegramDraft | None:
    if extractor is None:
        return None
    return extractor(message_text)
