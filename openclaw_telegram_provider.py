"""
openclaw_telegram_provider.py — OpenClaw-backed Telegram draft extraction.

This module calls a local OpenAI-compatible inference endpoint and converts the
result into Molly's structured Telegram draft format. If the call fails or the
response is unusable, the caller should fall back to heuristic Telegram NLU.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from urllib import error, request

import config
from telegram_extraction import ExtractedTelegramDraft, build_extraction_prompt

log = logging.getLogger(__name__)


def build_extractor_from_config():
    """Return an OpenClaw extractor when configured, otherwise None."""
    if config.TELEGRAM_EXTRACTOR_BACKEND != "openclaw":
        return None

    if not config.OPENCLAW_API_URL or not config.OPENCLAW_TELEGRAM_MODEL:
        log.warning(
            "Telegram extractor backend is set to openclaw, but OPENCLAW_API_URL "
            "or OPENCLAW_TELEGRAM_MODEL is missing. Falling back to heuristics."
        )
        return None

    def extractor(message_text: str) -> ExtractedTelegramDraft | None:
        return extract_draft_via_openclaw(message_text)

    return extractor


def extract_draft_via_openclaw(
    message_text: str,
    sender=None,
) -> ExtractedTelegramDraft | None:
    prompt = build_extraction_prompt(message_text)
    request_sender = sender or _send_chat_completion_request

    try:
        response_payload = request_sender(prompt)
        draft_payload = _extract_json_payload(response_payload)
        if draft_payload is None:
            return None
        return _draft_from_payload(draft_payload)
    except Exception as exc:
        log.warning("OpenClaw Telegram extraction failed: %s", exc)
        return None


def _send_chat_completion_request(prompt: str) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if config.OPENCLAW_API_KEY:
        headers["Authorization"] = f"Bearer {config.OPENCLAW_API_KEY}"

    payload = {
        "model": config.OPENCLAW_TELEGRAM_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You extract family scheduling intent from Telegram messages. "
                    "Return JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }

    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        config.OPENCLAW_API_URL,
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=config.OPENCLAW_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except error.URLError as exc:
        raise RuntimeError(f"Could not reach OpenClaw endpoint: {exc}") from exc

    return json.loads(raw)


def _extract_json_payload(response_payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(response_payload, dict):
        return None

    if "action" in response_payload:
        return response_payload

    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, list):
        text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
        content = "".join(text_parts)

    if not isinstance(content, str) or not content.strip():
        return None

    cleaned = _strip_code_fence(content.strip())
    return json.loads(cleaned)


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _draft_from_payload(payload: dict[str, Any]) -> ExtractedTelegramDraft:
    missing_fields = payload.get("missing_fields") or []
    if not isinstance(missing_fields, list):
        missing_fields = []

    confidence = payload.get("confidence")
    if isinstance(confidence, int):
        confidence = float(confidence)
    if not isinstance(confidence, float):
        confidence = None

    limit = payload.get("limit")
    if not isinstance(limit, int):
        limit = None

    return ExtractedTelegramDraft(
        action=_string_or_none(payload.get("action")),
        target_calendar=_string_or_none(payload.get("target_calendar")),
        title=_string_or_none(payload.get("title")),
        target_date_text=_string_or_none(payload.get("target_date_text")),
        time_text=_string_or_none(payload.get("time_text")),
        limit=limit,
        confidence=confidence,
        reasoning=_string_or_none(payload.get("reasoning")),
        missing_fields=[str(field) for field in missing_fields],
    )


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
