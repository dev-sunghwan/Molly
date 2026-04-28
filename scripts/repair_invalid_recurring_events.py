#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import config


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _find_invalid_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, calendar_key, summary, start_date, end_date, start_time, end_time,
               recurrence_json, created_at
        FROM local_events
        WHERE recurrence_json != '[]'
          AND start_date != end_date
        ORDER BY created_at, id
        """
    ).fetchall()


def _default_backup_path(db_path: Path) -> Path:
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    return db_path.with_name(f"{db_path.stem}.backup-before-recurring-repair-{stamp}{db_path.suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description='Repair invalid recurring local Molly events.')
    parser.add_argument('--apply', action='store_true', help='Apply fixes in-place.')
    parser.add_argument('--db-path', type=Path, default=Path(config.LOCAL_CALENDAR_DB_PATH))
    parser.add_argument('--backup-path', type=Path, help='Optional explicit backup path when using --apply.')
    args = parser.parse_args()

    db_path = args.db_path
    with _connect(db_path) as conn:
        rows = _find_invalid_rows(conn)

        if not rows:
            print('No invalid recurring rows found.')
            return 0

        print(f'Found {len(rows)} invalid recurring row(s).')
        for row in rows:
            print(
                f"FIX {row['id']} | {row['calendar_key']} | {row['summary']} | "
                f"{row['start_date']} {row['start_time']} -> {row['end_date']} {row['end_time']} | "
                f"recurrence={row['recurrence_json']}"
            )

        if not args.apply:
            print('Dry run only. Re-run with --apply to update end_date=start_date for these rows.')
            return 0

    backup_path = args.backup_path or _default_backup_path(db_path)
    shutil.copy2(db_path, backup_path)
    print(f'Backup created: {backup_path}')

    with _connect(db_path) as conn:
        rows = _find_invalid_rows(conn)
        conn.executemany(
            'UPDATE local_events SET end_date = start_date WHERE id = ?',
            [(row['id'],) for row in rows],
        )
        print(f'Repaired {len(rows)} invalid recurring row(s).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
