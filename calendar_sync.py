"""
Stage-1 local-to-Google calendar sync helpers.

This sync is intentionally conservative.
- Local calendar remains the source of truth.
- Google Calendar is treated as an optional mirror/export target.
- Only missing events are inserted.
- Existing Google events are never edited or deleted in this stage.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import config
import google_calendar_backend
import local_calendar_backend
import state_store
import utils


@dataclass
class SyncSummary:
    inserted: int = 0
    skipped_existing: int = 0
    skipped_unsupported: int = 0


@dataclass
class OutboxSyncSummary:
    processed: int = 0
    inserted: int = 0
    skipped_existing: int = 0
    unsupported: int = 0
    failed: int = 0


@dataclass
class LocalEventForSync:
    calendar_key: str
    summary: str
    start_date: date
    end_date: date
    start_time: str | None
    end_time: str | None
    all_day: bool
    recurrence: list[str]


def sync_local_to_google(
    start_date: date,
    end_date: date,
    *,
    dry_run: bool = True,
    calendar_keys: list[str] | None = None,
) -> tuple[SyncSummary, list[str]]:
    local_service = local_calendar_backend.authenticate()
    google_service = google_calendar_backend.authenticate()

    selected = set(calendar_keys or config.CALENDARS.keys())
    google_events_by_calendar = {
        calendar_key: google_calendar_backend.list_events_range(
            google_service,
            start_date,
            end_date,
        )
        for calendar_key in selected
    }

    summary = SyncSummary()
    details: list[str] = []

    for event in _iter_local_events(local_service, start_date, end_date, selected):
        if event.recurrence and not _is_supported_recurrence(event.recurrence):
            summary.skipped_unsupported += 1
            details.append(f"SKIP unsupported recurrence | {event.calendar_key} | {event.summary}")
            continue

        google_events = google_events_by_calendar[event.calendar_key]
        if _google_has_equivalent_event(google_events, event):
            summary.skipped_existing += 1
            details.append(f"SKIP existing | {event.calendar_key} | {event.summary}")
            continue

        if dry_run:
            summary.inserted += 1
            details.append(_format_detail("DRY-RUN insert", event))
            continue

        command = _to_google_add_command(event)
        google_calendar_backend.add_event(google_service, command)
        google_events.append(_local_event_to_googleish_dict(event))
        summary.inserted += 1
        details.append(_format_detail("INSERTED", event))

    return summary, details


def process_google_sync_outbox_once(
    *,
    limit: int = 10,
    max_attempts: int = 5,
    dry_run: bool = False,
) -> tuple[OutboxSyncSummary, list[str]]:
    pending = state_store.list_google_sync_outbox(status="pending", limit=limit)
    summary = OutboxSyncSummary()
    details: list[str] = []
    service = None

    for row in pending:
        if dry_run:
            _record_outbox_dry_run(row, summary, details)
            continue

        claimed = state_store.claim_google_sync_outbox_item(int(row["id"]))
        if claimed is None:
            continue

        summary.processed += 1
        if claimed["operation"] != "create":
            reason = f"Unsupported Google sync operation: {claimed['operation']}"
            state_store.mark_google_sync_outbox_unsupported(int(claimed["id"]), reason)
            summary.unsupported += 1
            details.append(f"UNSUPPORTED #{claimed['id']} | {reason}")
            continue

        try:
            event = _outbox_create_event_to_local_event(claimed)
            google_calendar_id = config.CALENDARS.get(event.calendar_key)
            idempotency_key = _outbox_idempotency_key(claimed)
            existing_mapping = state_store.get_google_event_mapping(idempotency_key)
            if existing_mapping is not None:
                state_store.mark_google_sync_outbox_done(
                    int(claimed["id"]),
                    google_calendar_id=existing_mapping["google_calendar_id"],
                    google_event_id=existing_mapping["google_event_id"],
                )
                summary.skipped_existing += 1
                details.append(
                    f"SKIP mapped #{claimed['id']} | {event.calendar_key} | {event.summary}"
                )
                continue

            if service is None:
                service = google_calendar_backend.authenticate()

            google_events = _google_events_for_calendar(
                service,
                event.calendar_key,
                event.start_date,
                event.end_date,
            )
            if _google_has_equivalent_event(google_events, event):
                google_event_id = _find_equivalent_google_event_id(google_events, event)
                state_store.upsert_google_event_mapping(
                    idempotency_key=idempotency_key,
                    operation=claimed["operation"],
                    google_calendar_id=google_calendar_id or "",
                    google_event_id=google_event_id,
                    local_event_id=claimed.get("local_event_id"),
                    outbox_id=int(claimed["id"]),
                )
                state_store.mark_google_sync_outbox_done(
                    int(claimed["id"]),
                    google_calendar_id=google_calendar_id,
                    google_event_id=google_event_id,
                )
                summary.skipped_existing += 1
                details.append(
                    f"SKIP existing #{claimed['id']} | {event.calendar_key} | {event.summary}"
                )
                continue

            command = _to_google_add_command(event)
            message = google_calendar_backend.add_event(service, command)
            if message.startswith("❌"):
                raise RuntimeError(message)
            google_events = _google_events_for_calendar(
                service,
                event.calendar_key,
                event.start_date,
                event.end_date,
            )
            google_event_id = _find_equivalent_google_event_id(google_events, event)
            state_store.upsert_google_event_mapping(
                idempotency_key=idempotency_key,
                operation=claimed["operation"],
                google_calendar_id=google_calendar_id or "",
                google_event_id=google_event_id,
                local_event_id=claimed.get("local_event_id"),
                outbox_id=int(claimed["id"]),
            )

            state_store.mark_google_sync_outbox_done(
                int(claimed["id"]),
                google_calendar_id=google_calendar_id,
                google_event_id=google_event_id,
            )
            summary.inserted += 1
            details.append(_format_detail(f"INSERTED #{claimed['id']}", event))
        except Exception as exc:
            retry = int(claimed["attempts"]) < max_attempts
            state_store.mark_google_sync_outbox_failed(int(claimed["id"]), str(exc), retry=retry)
            summary.failed += 1
            retry_label = "retry" if retry else "failed"
            details.append(f"FAILED #{claimed['id']} ({retry_label}) | {exc}")

    return summary, details


def _outbox_idempotency_key(row: dict) -> str:
    payload = row["payload"]
    relevant = {
        "operation": row["operation"],
        "local_event_id": row.get("local_event_id"),
        "target_calendar": payload.get("target_calendar"),
        "title": payload.get("title"),
        "target_date": payload.get("target_date"),
        "date_range": payload.get("date_range"),
        "time_range": payload.get("time_range"),
        "recurrence": payload.get("recurrence") or [],
        "metadata": {
            "all_day": (payload.get("metadata") or {}).get("all_day"),
        },
    }
    encoded = json.dumps(relevant, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _iter_local_events(service, start_date: date, end_date: date, selected: set[str]):
    seen: set[tuple] = set()
    for event in local_calendar_backend.list_events_range(service, start_date, end_date):
        calendar_key = _calendar_key_from_event(event)
        if calendar_key not in selected:
            continue
        key = (
            calendar_key,
            event.get("summary", ""),
            event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
            event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
            tuple(event.get("recurrence", []) or []),
        )
        if key in seen:
            continue
        seen.add(key)
        yield _normalize_local_event(calendar_key, event)


def _record_outbox_dry_run(row: dict, summary: OutboxSyncSummary, details: list[str]) -> None:
    summary.processed += 1
    if row["operation"] != "create":
        summary.unsupported += 1
        details.append(f"DRY-RUN unsupported #{row['id']} | {row['operation']}")
        return
    try:
        event = _outbox_create_event_to_local_event(row)
    except Exception as exc:
        summary.failed += 1
        details.append(f"DRY-RUN invalid #{row['id']} | {exc}")
        return
    summary.inserted += 1
    details.append(_format_detail(f"DRY-RUN insert #{row['id']}", event))


def _outbox_create_event_to_local_event(row: dict) -> LocalEventForSync:
    payload = row["payload"]
    calendar_key = str(payload.get("target_calendar") or "")
    if not calendar_key:
        raise ValueError("Missing target_calendar")
    if calendar_key not in config.CALENDARS:
        raise ValueError(f"Unknown calendar: {calendar_key}")

    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("Missing title")

    target_date = _parse_iso_date(payload.get("target_date"), "target_date")
    date_range = payload.get("date_range")
    end_date = (
        _parse_iso_date(date_range.get("end"), "date_range.end")
        if isinstance(date_range, dict) and date_range.get("end")
        else target_date
    )
    time_range = payload.get("time_range")
    all_day = bool(payload.get("metadata", {}).get("all_day", time_range is None))

    start_time = None
    end_time = None
    if not all_day:
        if not isinstance(time_range, dict):
            raise ValueError("Timed event is missing time_range")
        start_time = str(time_range.get("start") or "")
        end_time = str(time_range.get("end") or "")
        if not start_time or not end_time:
            raise ValueError("Timed event is missing start or end time")

    return LocalEventForSync(
        calendar_key=calendar_key,
        summary=title,
        start_date=target_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        all_day=all_day,
        recurrence=list(payload.get("recurrence") or []),
    )


def _parse_iso_date(value, field_name: str) -> date:
    if not value:
        raise ValueError(f"Missing {field_name}")
    return date.fromisoformat(str(value))


def _normalize_local_event(calendar_key: str, event: dict) -> LocalEventForSync:
    recurrence = list(event.get("recurrence") or [])
    start = event.get("start", {})
    end = event.get("end", {})

    if "dateTime" in start and "dateTime" in end:
        start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(utils.TZ)
        end_dt = datetime.fromisoformat(end["dateTime"]).astimezone(utils.TZ)
        return LocalEventForSync(
            calendar_key=calendar_key,
            summary=str(event.get("summary") or "(no title)"),
            start_date=start_dt.date(),
            end_date=end_dt.date(),
            start_time=start_dt.strftime("%H:%M"),
            end_time=end_dt.strftime("%H:%M"),
            all_day=False,
            recurrence=recurrence,
        )

    start_date_value = date.fromisoformat(start["date"])
    end_exclusive = date.fromisoformat(end["date"])
    return LocalEventForSync(
        calendar_key=calendar_key,
        summary=str(event.get("summary") or "(no title)"),
        start_date=start_date_value,
        end_date=end_exclusive - timedelta(days=1),
        start_time=None,
        end_time=None,
        all_day=True,
        recurrence=recurrence,
    )


def _calendar_key_from_event(event: dict) -> str:
    display = str(event.get("_calendar_name") or "").lower()
    if display in config.CALENDAR_DISPLAY_NAMES:
        return display
    for key, label in config.CALENDAR_DISPLAY_NAMES.items():
        if display == label.lower():
            return key
    return display


def _google_has_equivalent_event(events: list[dict], candidate: LocalEventForSync) -> bool:
    for event in events:
        if str(event.get("summary") or "") != candidate.summary:
            continue
        if list(event.get("recurrence") or []) != list(candidate.recurrence or []):
            continue

        start = event.get("start", {})
        end = event.get("end", {})
        if candidate.all_day:
            if start.get("date") != candidate.start_date.isoformat():
                continue
            expected_end = (candidate.end_date + timedelta(days=1)).isoformat()
            if end.get("date") != expected_end:
                continue
            return True

        if "dateTime" not in start or "dateTime" not in end:
            continue
        start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(utils.TZ)
        end_dt = datetime.fromisoformat(end["dateTime"]).astimezone(utils.TZ)
        if (
            start_dt.date() == candidate.start_date
            and end_dt.date() == candidate.end_date
            and start_dt.strftime("%H:%M") == candidate.start_time
            and end_dt.strftime("%H:%M") == candidate.end_time
        ):
            return True
    return False


def _find_equivalent_google_event_id(
    events: list[dict],
    candidate: LocalEventForSync,
) -> str | None:
    for event in events:
        if _google_event_matches(event, candidate):
            return event.get("id")
    return None


def _google_event_matches(event: dict, candidate: LocalEventForSync) -> bool:
    if str(event.get("summary") or "") != candidate.summary:
        return False
    if list(event.get("recurrence") or []) != list(candidate.recurrence or []):
        return False

    start = event.get("start", {})
    end = event.get("end", {})
    if candidate.all_day:
        if start.get("date") != candidate.start_date.isoformat():
            return False
        expected_end = (candidate.end_date + timedelta(days=1)).isoformat()
        return end.get("date") == expected_end

    if "dateTime" not in start or "dateTime" not in end:
        return False
    start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(utils.TZ)
    end_dt = datetime.fromisoformat(end["dateTime"]).astimezone(utils.TZ)
    return (
        start_dt.date() == candidate.start_date
        and end_dt.date() == candidate.end_date
        and start_dt.strftime("%H:%M") == candidate.start_time
        and end_dt.strftime("%H:%M") == candidate.end_time
    )


def _google_events_for_calendar(
    service,
    calendar_key: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    events = google_calendar_backend.list_events_range(service, start_date, end_date)
    return [
        event
        for event in events
        if _calendar_key_from_event(event) == calendar_key
    ]


def _to_google_add_command(event: LocalEventForSync) -> dict:
    command = {
        "calendar": event.calendar_key,
        "calendar_display": config.CALENDAR_DISPLAY_NAMES.get(
            event.calendar_key,
            event.calendar_key,
        ),
        "title": event.summary,
        "date": event.start_date,
        "all_day": event.all_day,
    }
    if event.recurrence:
        command["recurrence"] = list(event.recurrence)
    if event.end_date != event.start_date:
        command["end_date"] = event.end_date
    if not event.all_day:
        command["start"] = event.start_time
        command["end"] = event.end_time
    return command


def _local_event_to_googleish_dict(event: LocalEventForSync) -> dict:
    if event.all_day:
        return {
            "summary": event.summary,
            "start": {"date": event.start_date.isoformat()},
            "end": {"date": (event.end_date + timedelta(days=1)).isoformat()},
            "recurrence": list(event.recurrence),
        }
    start_dt = utils.make_datetime(event.start_date, event.start_time or "00:00")
    end_dt = utils.make_datetime(event.end_date, event.end_time or "00:00")
    return {
        "summary": event.summary,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": config.TIMEZONE},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": config.TIMEZONE},
        "recurrence": list(event.recurrence),
    }


def _is_supported_recurrence(recurrence: list[str]) -> bool:
    if not recurrence:
        return True
    if len(recurrence) != 1:
        return False
    rule = recurrence[0]
    return "FREQ=WEEKLY" in rule and "BYDAY=" in rule


def _format_detail(prefix: str, event: LocalEventForSync) -> str:
    if event.all_day:
        if event.start_date == event.end_date:
            when = event.start_date.isoformat()
        else:
            when = f"{event.start_date.isoformat()}..{event.end_date.isoformat()}"
    else:
        when = f"{event.start_date.isoformat()} {event.start_time}-{event.end_time}"
        if event.end_date != event.start_date:
            when = (
                f"{event.start_date.isoformat()} {event.start_time}.."
                f"{event.end_date.isoformat()} {event.end_time}"
            )
    recurring = " recurring" if event.recurrence else ""
    return f"{prefix} | {event.calendar_key} | {event.summary} | {when}{recurring}"
