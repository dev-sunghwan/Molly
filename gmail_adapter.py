"""
gmail_adapter.py — Minimal Gmail ingestion adapter for Molly.

Phase 4 introduces a safe read-only ingestion boundary:
- list recent inbox messages
- fetch and normalize message content
- rely on state_store to avoid reprocessing the same message
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from email.utils import parseaddr
from typing import Any


@dataclass
class GmailMessage:
    message_id: str
    thread_id: str | None
    subject: str
    sender: str
    snippet: str
    body_text: str
    internal_date: str | None
    raw_payload: dict[str, Any]


def list_message_ids(service, max_results: int = 10, query: str = "in:inbox") -> list[str]:
    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    return [item["id"] for item in result.get("messages", [])]


def fetch_message(service, message_id: str) -> GmailMessage:
    payload = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    return normalize_message(payload)


def normalize_message(payload: dict[str, Any]) -> GmailMessage:
    headers = _header_map(payload.get("payload", {}).get("headers", []))
    body_text = _extract_body_text(payload.get("payload", {})).strip()
    return GmailMessage(
        message_id=payload["id"],
        thread_id=payload.get("threadId"),
        subject=headers.get("subject", ""),
        sender=headers.get("from", ""),
        snippet=payload.get("snippet", ""),
        body_text=body_text,
        internal_date=payload.get("internalDate"),
        raw_payload=payload,
    )


def extract_sender_email(sender_header: str) -> str | None:
    _, email_address = parseaddr(sender_header or "")
    normalized = email_address.strip().lower()
    return normalized or None


def _header_map(headers: list[dict[str, str]]) -> dict[str, str]:
    return {header["name"].lower(): header["value"] for header in headers}


def _extract_body_text(payload: dict[str, Any]) -> str:
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")

    if mime_type == "text/plain" and data:
        return _decode_body(data)

    parts = payload.get("parts", [])
    plain_parts = [part for part in parts if part.get("mimeType") == "text/plain"]
    other_parts = [part for part in parts if part.get("mimeType") != "text/plain"]

    for part in plain_parts:
        text = _extract_body_text(part)
        if text:
            return text

    for part in other_parts:
        text = _extract_body_text(part)
        if text:
            return text

    if data:
        return _decode_body(data)

    return ""


def _decode_body(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")
