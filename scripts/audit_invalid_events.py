#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import config


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _recurrence_spans_multiple_days(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, calendar_key, summary, start_date, end_date, start_time, end_time,
               recurrence_json, created_at
        FROM local_events
        WHERE recurrence_json != '[]'
          AND start_date != end_date
        ORDER BY created_at, id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _invalid_recurrence_rules(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, calendar_key, summary, start_date, end_date, start_time, end_time,
               recurrence_json, created_at
        FROM local_events
        WHERE recurrence_json != '[]'
        ORDER BY created_at, id
        """
    ).fetchall()

    bad: list[dict] = []
    for row in rows:
        payload = dict(row)
        try:
            recurrence = json.loads(payload['recurrence_json'] or '[]')
        except json.JSONDecodeError:
            payload['issue'] = 'recurrence_json_not_valid_json'
            bad.append(payload)
            continue

        if not isinstance(recurrence, list) or len(recurrence) != 1:
            payload['issue'] = 'unsupported_recurrence_shape'
            bad.append(payload)
            continue

        rule = recurrence[0]
        if not isinstance(rule, str) or not rule.startswith('RRULE:FREQ=WEEKLY;BYDAY='):
            payload['issue'] = 'unsupported_recurrence_rule'
            bad.append(payload)
            continue

        byday = rule.split('BYDAY=', 1)[-1].strip()
        if byday not in {'MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'}:
            payload['issue'] = 'unsupported_byday'
            bad.append(payload)
    return bad


def _timed_events_with_missing_end(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, calendar_key, summary, start_date, end_date, start_time, end_time,
               recurrence_json, created_at
        FROM local_events
        WHERE all_day = 0
          AND start_time IS NOT NULL
          AND (end_time IS NULL OR trim(end_time) = '')
        ORDER BY created_at, id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _print_section(title: str, rows: list[dict]) -> None:
    print(f'[{title}] {len(rows)}')
    for row in rows:
        extra = f" | issue={row['issue']}" if 'issue' in row else ''
        print(
            f"- {row['id']} | {row['calendar_key']} | {row['summary']} | "
            f"{row['start_date']} {row['start_time']} -> {row['end_date']} {row['end_time']}"
            f" | recurrence={row['recurrence_json']}{extra}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit local Molly calendar data for suspicious events.')
    parser.add_argument('--db-path', type=Path, default=Path(config.LOCAL_CALENDAR_DB_PATH))
    args = parser.parse_args()

    with _connect(args.db_path) as conn:
        recurrence_spans = _recurrence_spans_multiple_days(conn)
        invalid_rules = _invalid_recurrence_rules(conn)
        timed_missing_end = _timed_events_with_missing_end(conn)

    _print_section('recurring_spans_multiple_days', recurrence_spans)
    _print_section('invalid_recurrence_rules', invalid_rules)
    _print_section('timed_events_missing_end', timed_missing_end)

    total_issues = len(recurrence_spans) + len(invalid_rules) + len(timed_missing_end)
    print(f'\nTOTAL_ISSUES {total_issues}')
    return 1 if total_issues else 0


if __name__ == '__main__':
    raise SystemExit(main())
