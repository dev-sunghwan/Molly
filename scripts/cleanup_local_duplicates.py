#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from pathlib import Path

import config


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _recurrence_rank(row: sqlite3.Row) -> int:
    recurrence_json = row["recurrence_json"] or "[]"
    return 1 if recurrence_json != "[]" else 0


def _source_rank(row: sqlite3.Row) -> int:
    return 1 if row["source_backend"] or row["source_event_id"] else 0


def _group_key(row: sqlite3.Row) -> tuple:
    return (
        row["calendar_key"],
        row["summary"].strip().lower(),
        row["start_date"],
        row["end_date"],
        row["start_time"],
        row["end_time"],
        row["all_day"],
    )


def _keep_sort_key(row: sqlite3.Row) -> tuple:
    return (
        _recurrence_rank(row),
        _source_rank(row),
        -(len(row["summary"] or "")),
        row["created_at"] or "",
        row["id"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean duplicate local Molly events.")
    parser.add_argument("--dry-run", action="store_true", help="Show duplicates without deleting them.")
    args = parser.parse_args()

    with _connect(config.LOCAL_CALENDAR_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, calendar_key, summary, start_date, end_date, start_time, end_time,
                   all_day, recurrence_json, source_backend, source_event_id, created_at
            FROM local_events
            ORDER BY created_at, id
            """
        ).fetchall()

        groups: dict[tuple, list[sqlite3.Row]] = defaultdict(list)
        for row in rows:
            groups[_group_key(row)].append(row)

        duplicate_groups = [group for group in groups.values() if len(group) > 1]
        duplicate_groups.sort(key=lambda group: (_group_key(group[0]), len(group)))

        if not duplicate_groups:
            print("No duplicate groups found.")
            return 0

        deleted_ids: list[str] = []
        for group in duplicate_groups:
            keep = max(group, key=_keep_sort_key)
            victims = [row for row in group if row["id"] != keep["id"]]
            print(
                f"KEEP {keep['id']} | {keep['calendar_key']} | {keep['summary']} | "
                f"{keep['start_date']} {keep['start_time']} -> {keep['end_date']} {keep['end_time']} | "
                f"recurrence={keep['recurrence_json']}"
            )
            for victim in victims:
                print(
                    f"DROP {victim['id']} | {victim['calendar_key']} | {victim['summary']} | "
                    f"{victim['start_date']} {victim['start_time']} -> {victim['end_date']} {victim['end_time']} | "
                    f"recurrence={victim['recurrence_json']}"
                )
                deleted_ids.append(victim["id"])

        if args.dry_run:
            print(f"Dry run complete. Would delete {len(deleted_ids)} rows across {len(duplicate_groups)} groups.")
            return 0

        conn.executemany("DELETE FROM local_events WHERE id = ?", [(row_id,) for row_id in deleted_ids])
        print(f"Deleted {len(deleted_ids)} rows across {len(duplicate_groups)} groups.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
