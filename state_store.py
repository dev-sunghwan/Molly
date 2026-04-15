"""
state_store.py — SQLite-backed persistence for Molly workflow state.

Phase 3 introduced workflow state storage. Phase 4 extends it with processed
input tracking for Gmail ingestion and future deduplication.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date

import config
from intent_models import (
    DateRange,
    ExecutionResult,
    IntentAction,
    IntentResolution,
    IntentSource,
    ResolutionStatus,
    ScheduleIntent,
    TimeRange,
)


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_clarifications (
                user_id INTEGER PRIMARY KEY,
                resolution_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                success INTEGER NOT NULL,
                message TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_inputs (
                source TEXT NOT NULL,
                external_id TEXT NOT NULL,
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (source, external_id)
            )
            """
        )
        conn.commit()


def save_pending_clarification(user_id: int, resolution: IntentResolution) -> None:
    payload = json.dumps(_resolution_to_dict(resolution), ensure_ascii=True, sort_keys=True)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO pending_clarifications (user_id, resolution_json, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                resolution_json = excluded.resolution_json,
                created_at = CURRENT_TIMESTAMP
            """,
            (user_id, payload),
        )
        conn.commit()


def load_pending_clarification(user_id: int) -> IntentResolution | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT resolution_json FROM pending_clarifications WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return _resolution_from_dict(json.loads(row[0]))


def clear_pending_clarification(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM pending_clarifications WHERE user_id = ?", (user_id,))
        conn.commit()


def record_execution(user_id: int | None, result: ExecutionResult) -> None:
    payload = json.dumps(result.metadata, ensure_ascii=True, sort_keys=True)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO execution_log (user_id, action, success, message, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                result.action.value,
                1 if result.success else 0,
                result.message,
                payload,
            ),
        )
        conn.commit()


def list_execution_log(limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT user_id, action, success, message, metadata_json, created_at
            FROM execution_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "user_id": row[0],
            "action": row[1],
            "success": bool(row[2]),
            "message": row[3],
            "metadata": json.loads(row[4]),
            "created_at": row[5],
        }
        for row in rows
    ]


def mark_processed_input(
    source: str,
    external_id: str,
    status: str,
    metadata: dict | None = None,
) -> None:
    payload = json.dumps(metadata or {}, ensure_ascii=True, sort_keys=True)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO processed_inputs (source, external_id, status, metadata_json, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(source, external_id) DO UPDATE SET
                status = excluded.status,
                metadata_json = excluded.metadata_json
            """,
            (source, external_id, status, payload),
        )
        conn.commit()


def get_processed_input(source: str, external_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT source, external_id, status, metadata_json, created_at
            FROM processed_inputs
            WHERE source = ? AND external_id = ?
            """,
            (source, external_id),
        ).fetchone()
    if row is None:
        return None
    return {
        "source": row[0],
        "external_id": row[1],
        "status": row[2],
        "metadata": json.loads(row[3]),
        "created_at": row[4],
    }


def is_processed_input(source: str, external_id: str) -> bool:
    return get_processed_input(source, external_id) is not None


def _connect() -> sqlite3.Connection:
    config.STATE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(config.STATE_DB_PATH)


def _resolution_to_dict(resolution: IntentResolution) -> dict:
    return {
        "status": resolution.status.value,
        "intent": _intent_to_dict(resolution.intent),
        "missing_fields": list(resolution.missing_fields),
        "clarification_prompt": resolution.clarification_prompt,
        "reason": resolution.reason,
    }


def _resolution_from_dict(payload: dict) -> IntentResolution:
    return IntentResolution(
        status=ResolutionStatus(payload["status"]),
        intent=_intent_from_dict(payload["intent"]),
        missing_fields=list(payload.get("missing_fields", [])),
        clarification_prompt=payload.get("clarification_prompt"),
        reason=payload.get("reason"),
    )


def _intent_to_dict(intent: ScheduleIntent) -> dict:
    return {
        "action": intent.action.value,
        "source": intent.source.value,
        "raw_input": intent.raw_input,
        "target_calendar": intent.target_calendar,
        "title": intent.title,
        "target_date": intent.target_date.isoformat() if intent.target_date else None,
        "date_range": _date_range_to_dict(intent.date_range),
        "time_range": _time_range_to_dict(intent.time_range),
        "recurrence": list(intent.recurrence),
        "search_query": intent.search_query,
        "help_topic": intent.help_topic,
        "limit": intent.limit,
        "changes": dict(intent.changes),
        "metadata": dict(intent.metadata),
    }


def _intent_from_dict(payload: dict) -> ScheduleIntent:
    return ScheduleIntent(
        action=IntentAction(payload["action"]),
        source=IntentSource(payload["source"]),
        raw_input=payload.get("raw_input", ""),
        target_calendar=payload.get("target_calendar"),
        title=payload.get("title"),
        target_date=_date_from_str(payload.get("target_date")),
        date_range=_date_range_from_dict(payload.get("date_range")),
        time_range=_time_range_from_dict(payload.get("time_range")),
        recurrence=list(payload.get("recurrence", [])),
        search_query=payload.get("search_query"),
        help_topic=payload.get("help_topic"),
        limit=payload.get("limit"),
        changes=dict(payload.get("changes", {})),
        metadata=dict(payload.get("metadata", {})),
    )


def _date_from_str(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _date_range_to_dict(value: DateRange | None) -> dict | None:
    if value is None:
        return None
    return {"start": value.start.isoformat(), "end": value.end.isoformat()}


def _date_range_from_dict(value: dict | None) -> DateRange | None:
    if value is None:
        return None
    return DateRange(start=date.fromisoformat(value["start"]), end=date.fromisoformat(value["end"]))


def _time_range_to_dict(value: TimeRange | None) -> dict | None:
    if value is None:
        return None
    return {"start": value.start, "end": value.end}


def _time_range_from_dict(value: dict | None) -> TimeRange | None:
    if value is None:
        return None
    return TimeRange(start=value["start"], end=value["end"])
