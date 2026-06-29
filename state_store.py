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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                decision_status TEXT NOT NULL,
                reason TEXT NOT NULL,
                summary TEXT,
                candidate_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                notified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                source_message_id TEXT,
                source_user_id TEXT,
                source_user_name TEXT,
                source_channel_id TEXT,
                raw_text TEXT,
                raw_payload_json TEXT NOT NULL,
                status TEXT NOT NULL,
                parser_version TEXT,
                structured_json TEXT,
                validation_error TEXT,
                execution_result_json TEXT,
                reply_status TEXT,
                reply_error TEXT,
                reply_attempts INTEGER NOT NULL DEFAULT 0,
                last_reply_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_column(conn, "commands", "reply_status", "TEXT")
        _ensure_column(conn, "commands", "reply_error", "TEXT")
        _ensure_column(conn, "commands", "reply_attempts", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "commands", "last_reply_at", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS google_sync_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                local_event_id TEXT,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                google_calendar_id TEXT,
                google_event_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS google_event_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT NOT NULL UNIQUE,
                local_event_id TEXT,
                outbox_id INTEGER,
                operation TEXT NOT NULL,
                google_calendar_id TEXT NOT NULL,
                google_event_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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


def record_inbound_command(
    *,
    request_id: str,
    source: str,
    raw_payload: dict,
    raw_text: str | None = None,
    source_message_id: str | None = None,
    source_user_id: str | None = None,
    source_user_name: str | None = None,
    source_channel_id: str | None = None,
    status: str = "received",
) -> dict:
    """
    Persist an inbound command before parsing or execution.

    `request_id` is idempotent: a duplicate insert returns the original row
    without overwriting the first persisted payload.
    """
    payload = json.dumps(raw_payload, ensure_ascii=True, sort_keys=True)
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO commands (
                request_id, source, source_message_id, source_user_id,
                source_user_name, source_channel_id, raw_text, raw_payload_json,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                source,
                source_message_id,
                source_user_id,
                source_user_name,
                source_channel_id,
                raw_text,
                payload,
                status,
            ),
        )
        conn.commit()

    stored = get_command_by_request_id(request_id)
    if stored is None:
        raise RuntimeError(f"Failed to persist inbound command request_id={request_id}")
    return stored


def get_command_by_request_id(request_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, request_id, source, source_message_id, source_user_id,
                   source_user_name, source_channel_id, raw_text,
                   raw_payload_json, status, parser_version, structured_json,
                   validation_error, execution_result_json, reply_status,
                   reply_error, reply_attempts, last_reply_at, created_at, updated_at
            FROM commands
            WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()
    return _row_to_command(row)


def list_commands(
    *,
    status: str | None = None,
    source: str | None = None,
    limit: int = 50,
) -> list[dict]:
    query = [
        """
        SELECT id, request_id, source, source_message_id, source_user_id,
               source_user_name, source_channel_id, raw_text,
               raw_payload_json, status, parser_version, structured_json,
               validation_error, execution_result_json, reply_status,
               reply_error, reply_attempts, last_reply_at, created_at, updated_at
        FROM commands
        """
    ]
    params: list[object] = []
    where: list[str] = []
    if status is not None:
        where.append("status = ?")
        params.append(status)
    if source is not None:
        where.append("source = ?")
        params.append(source)
    if where:
        query.append("WHERE " + " AND ".join(where))
    query.append("ORDER BY id DESC LIMIT ?")
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute("\n".join(query), tuple(params)).fetchall()
    return [_row_to_command(row) for row in rows if row is not None]


def count_commands_by_status(*, source: str | None = None) -> dict[str, int]:
    query = ["SELECT status, COUNT(*) FROM commands"]
    params: list[object] = []
    if source is not None:
        query.append("WHERE source = ?")
        params.append(source)
    query.append("GROUP BY status ORDER BY status")

    with _connect() as conn:
        rows = conn.execute("\n".join(query), tuple(params)).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def update_command_reply_status(
    request_id: str,
    reply_status: str,
    *,
    reply_error: str | None = None,
) -> dict:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE commands
            SET reply_status = ?,
                reply_error = ?,
                reply_attempts = reply_attempts + 1,
                last_reply_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE request_id = ?
            """,
            (reply_status, reply_error, request_id),
        )
        conn.commit()

    stored = get_command_by_request_id(request_id)
    if stored is None:
        raise KeyError(f"Unknown command request_id={request_id}")
    return stored


def update_command_status(
    request_id: str,
    status: str,
    *,
    parser_version: str | None = None,
    structured_payload: dict | None = None,
    validation_error: str | None = None,
    execution_result: dict | None = None,
) -> dict:
    structured_json = (
        json.dumps(structured_payload, ensure_ascii=True, sort_keys=True)
        if structured_payload is not None
        else None
    )
    execution_result_json = (
        json.dumps(execution_result, ensure_ascii=True, sort_keys=True)
        if execution_result is not None
        else None
    )
    with _connect() as conn:
        conn.execute(
            """
            UPDATE commands
            SET status = ?,
                parser_version = COALESCE(?, parser_version),
                structured_json = COALESCE(?, structured_json),
                validation_error = COALESCE(?, validation_error),
                execution_result_json = COALESCE(?, execution_result_json),
                updated_at = CURRENT_TIMESTAMP
            WHERE request_id = ?
            """,
            (
                status,
                parser_version,
                structured_json,
                validation_error,
                execution_result_json,
                request_id,
            ),
        )
        conn.commit()

    stored = get_command_by_request_id(request_id)
    if stored is None:
        raise KeyError(f"Unknown command request_id={request_id}")
    return stored


def enqueue_google_sync(
    *,
    operation: str,
    payload: dict,
    local_event_id: str | None = None,
    status: str = "pending",
) -> int:
    payload_json = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO google_sync_outbox (
                operation, local_event_id, payload_json, status
            )
            VALUES (?, ?, ?, ?)
            """,
            (operation, local_event_id, payload_json, status),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_google_sync_outbox(status: str | None = None, limit: int = 50) -> list[dict]:
    query = [
        """
        SELECT id, operation, local_event_id, payload_json, status, attempts,
               last_error, google_calendar_id, google_event_id, created_at, updated_at
        FROM google_sync_outbox
        """
    ]
    params: list[object] = []
    if status is not None:
        query.append("WHERE status = ?")
        params.append(status)
    query.append("ORDER BY id ASC LIMIT ?")
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute("\n".join(query), tuple(params)).fetchall()
    return [_row_to_google_sync_outbox(row) for row in rows if row is not None]


def count_google_sync_outbox_by_status() -> dict[str, int]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT status, COUNT(*)
            FROM google_sync_outbox
            GROUP BY status
            ORDER BY status
            """
        ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def get_google_sync_outbox_item(outbox_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, operation, local_event_id, payload_json, status, attempts,
                   last_error, google_calendar_id, google_event_id, created_at, updated_at
            FROM google_sync_outbox
            WHERE id = ?
            """,
            (outbox_id,),
        ).fetchone()
    return _row_to_google_sync_outbox(row) if row is not None else None


def claim_google_sync_outbox_item(outbox_id: int) -> dict | None:
    """
    Move a pending outbox row to processing.

    The status predicate prevents a second worker from claiming a row that is no
    longer pending. This is intentionally small and SQLite-friendly.
    """
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE google_sync_outbox
            SET status = 'processing',
                attempts = attempts + 1,
                last_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'pending'
            """,
            (outbox_id,),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
    item = get_google_sync_outbox_item(outbox_id)
    if item is None or item["status"] != "processing":
        return None
    return item


def mark_google_sync_outbox_done(
    outbox_id: int,
    *,
    google_calendar_id: str | None = None,
    google_event_id: str | None = None,
) -> dict:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE google_sync_outbox
            SET status = 'done',
                last_error = NULL,
                google_calendar_id = COALESCE(?, google_calendar_id),
                google_event_id = COALESCE(?, google_event_id),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (google_calendar_id, google_event_id, outbox_id),
        )
        conn.commit()
    item = get_google_sync_outbox_item(outbox_id)
    if item is None:
        raise KeyError(f"Unknown google sync outbox id={outbox_id}")
    return item


def mark_google_sync_outbox_failed(
    outbox_id: int,
    error: str,
    *,
    retry: bool = True,
) -> dict:
    status = "pending" if retry else "failed"
    with _connect() as conn:
        conn.execute(
            """
            UPDATE google_sync_outbox
            SET status = ?,
                last_error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, error, outbox_id),
        )
        conn.commit()
    item = get_google_sync_outbox_item(outbox_id)
    if item is None:
        raise KeyError(f"Unknown google sync outbox id={outbox_id}")
    return item


def mark_google_sync_outbox_unsupported(outbox_id: int, reason: str) -> dict:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE google_sync_outbox
            SET status = 'unsupported',
                last_error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reason, outbox_id),
        )
        conn.commit()
    item = get_google_sync_outbox_item(outbox_id)
    if item is None:
        raise KeyError(f"Unknown google sync outbox id={outbox_id}")
    return item


def upsert_google_event_mapping(
    *,
    idempotency_key: str,
    operation: str,
    google_calendar_id: str,
    google_event_id: str | None = None,
    local_event_id: str | None = None,
    outbox_id: int | None = None,
) -> dict:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO google_event_mappings (
                idempotency_key, local_event_id, outbox_id, operation,
                google_calendar_id, google_event_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(idempotency_key) DO UPDATE SET
                local_event_id = COALESCE(excluded.local_event_id, local_event_id),
                outbox_id = COALESCE(excluded.outbox_id, outbox_id),
                operation = excluded.operation,
                google_calendar_id = excluded.google_calendar_id,
                google_event_id = COALESCE(excluded.google_event_id, google_event_id),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                idempotency_key,
                local_event_id,
                outbox_id,
                operation,
                google_calendar_id,
                google_event_id,
            ),
        )
        conn.commit()

    mapping = get_google_event_mapping(idempotency_key)
    if mapping is None:
        raise RuntimeError(f"Failed to persist Google event mapping: {idempotency_key}")
    return mapping


def get_google_event_mapping(idempotency_key: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, idempotency_key, local_event_id, outbox_id, operation,
                   google_calendar_id, google_event_id, created_at, updated_at
            FROM google_event_mappings
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
    return _row_to_google_event_mapping(row)


def save_email_candidate(
    message_id: str,
    status: str,
    reason: str,
    summary: str | None,
    candidate_payload: dict,
    metadata: dict | None = None,
) -> int:
    existing = get_email_candidate_by_message_id(message_id)
    decision_status = _candidate_decision_status(status)
    candidate_json = json.dumps(candidate_payload, ensure_ascii=True, sort_keys=True)
    metadata_json = json.dumps(metadata or {}, ensure_ascii=True, sort_keys=True)

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO email_candidates (
                message_id, status, decision_status, reason, summary,
                candidate_json, metadata_json, notified
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, 0))
            ON CONFLICT(message_id) DO UPDATE SET
                status = excluded.status,
                decision_status = excluded.decision_status,
                reason = excluded.reason,
                summary = excluded.summary,
                candidate_json = excluded.candidate_json,
                metadata_json = excluded.metadata_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                message_id,
                status,
                decision_status,
                reason,
                summary,
                candidate_json,
                metadata_json,
                1 if existing and existing.get("notified") else 0,
            ),
        )
        conn.commit()

    stored = get_email_candidate_by_message_id(message_id)
    if stored is None:
        raise RuntimeError(f"Failed to save email candidate for message_id={message_id}")
    return int(stored["id"])


def get_email_candidate(candidate_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, message_id, status, decision_status, reason, summary,
                   candidate_json, metadata_json, notified, created_at, updated_at
            FROM email_candidates
            WHERE id = ?
            """,
            (candidate_id,),
        ).fetchone()
    return _row_to_email_candidate(row)


def get_email_candidate_by_message_id(message_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, message_id, status, decision_status, reason, summary,
                   candidate_json, metadata_json, notified, created_at, updated_at
            FROM email_candidates
            WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()
    return _row_to_email_candidate(row)


def list_email_candidates(
    decision_status: str | None = None,
    notified: bool | None = None,
    limit: int = 50,
) -> list[dict]:
    query = [
        """
        SELECT id, message_id, status, decision_status, reason, summary,
               candidate_json, metadata_json, notified, created_at, updated_at
        FROM email_candidates
        """
    ]
    params: list[object] = []
    where: list[str] = []
    if decision_status is not None:
        where.append("decision_status = ?")
        params.append(decision_status)
    if notified is not None:
        where.append("notified = ?")
        params.append(1 if notified else 0)
    if where:
        query.append("WHERE " + " AND ".join(where))
    query.append("ORDER BY id DESC LIMIT ?")
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute("\n".join(query), tuple(params)).fetchall()
    return [_row_to_email_candidate(row) for row in rows if row is not None]


def update_email_candidate_decision(
    candidate_id: int,
    decision_status: str,
    metadata_updates: dict | None = None,
) -> None:
    existing = get_email_candidate(candidate_id)
    if existing is None:
        raise KeyError(f"Unknown email candidate id={candidate_id}")
    merged_metadata = dict(existing["metadata"])
    if metadata_updates:
        merged_metadata.update(metadata_updates)
    with _connect() as conn:
        conn.execute(
            """
            UPDATE email_candidates
            SET decision_status = ?,
                metadata_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                decision_status,
                json.dumps(merged_metadata, ensure_ascii=True, sort_keys=True),
                candidate_id,
            ),
        )
        conn.commit()


def mark_email_candidate_notified(candidate_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE email_candidates
            SET notified = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (candidate_id,),
        )
        conn.commit()


def _connect() -> sqlite3.Connection:
    config.STATE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(config.STATE_DB_PATH)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    existing = {
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column in existing:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _candidate_decision_status(status: str) -> str:
    if status == "ready":
        return "pending_confirmation"
    if status == "needs_clarification":
        return "needs_clarification"
    return "ignored"


def _row_to_email_candidate(row) -> dict | None:
    if row is None:
        return None
    payload = json.loads(row[6])
    return {
        "id": row[0],
        "message_id": row[1],
        "status": row[2],
        "decision_status": row[3],
        "reason": row[4],
        "summary": row[5],
        "candidate": payload,
        "metadata": json.loads(row[7]),
        "notified": bool(row[8]),
        "created_at": row[9],
        "updated_at": row[10],
    }


def _row_to_command(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": row[0],
        "request_id": row[1],
        "source": row[2],
        "source_message_id": row[3],
        "source_user_id": row[4],
        "source_user_name": row[5],
        "source_channel_id": row[6],
        "raw_text": row[7],
        "raw_payload": json.loads(row[8]),
        "status": row[9],
        "parser_version": row[10],
        "structured_payload": json.loads(row[11]) if row[11] else None,
        "validation_error": row[12],
        "execution_result": json.loads(row[13]) if row[13] else None,
        "reply_status": row[14],
        "reply_error": row[15],
        "reply_attempts": row[16],
        "last_reply_at": row[17],
        "created_at": row[18],
        "updated_at": row[19],
    }


def _row_to_google_sync_outbox(row) -> dict:
    return {
        "id": row[0],
        "operation": row[1],
        "local_event_id": row[2],
        "payload": json.loads(row[3]),
        "status": row[4],
        "attempts": row[5],
        "last_error": row[6],
        "google_calendar_id": row[7],
        "google_event_id": row[8],
        "created_at": row[9],
        "updated_at": row[10],
    }


def _row_to_google_event_mapping(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": row[0],
        "idempotency_key": row[1],
        "local_event_id": row[2],
        "outbox_id": row[3],
        "operation": row[4],
        "google_calendar_id": row[5],
        "google_event_id": row[6],
        "created_at": row[7],
        "updated_at": row[8],
    }


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
