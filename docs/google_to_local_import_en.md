# Google To Local Calendar Import

## Purpose

The recovered Google Calendar is not being restored as Molly's primary system of record.  
The purpose of this step is to safely pull already-entered family schedule data from Google Calendar into the local calendar database.

For now, Google should be treated as:

- a migration source for previously entered events
- an optional email or external intake channel if needed

## What Was Added

- `calendar_import.py`
- `scripts/import_google_calendar_to_local.py`

This flow:

1. authenticates to Google Calendar
2. connects to Molly's local calendar DB
3. reads events from each family calendar
4. inserts them into local storage safely

## Safety Measures

### 1. Re-runnable import

Google event IDs are stored alongside imported local event records:

- `source_backend`
- `source_event_id`

If the same Google event is encountered again, the importer skips it instead of inserting a duplicate.

That makes repeated import runs much safer.

### 2. Conservative recurrence support

Only recurrence patterns that the current local backend can reproduce safely are imported.

Currently supported:

- a single `RRULE`
- `FREQ=WEEKLY`
- includes `BYDAY=...`

Currently skipped:

- more complex recurrence patterns
- recurrence rules with exceptions such as `EXDATE`
- shapes the local backend cannot reproduce faithfully yet

At this stage, the priority is to import less rather than import incorrectly.

## How To Run

Dry-run first:

```bash
./.venv/bin/python scripts/import_google_calendar_to_local.py --dry-run
```

Real import:

```bash
./.venv/bin/python scripts/import_google_calendar_to_local.py
```

A custom range can also be specified:

```bash
./.venv/bin/python scripts/import_google_calendar_to_local.py --start 2025-01-01 --end 2027-12-31
```

The default window is:

- start: 180 days before today
- end: 365 days after today

## Current Judgment

This import path is not a move back to Google as the main backend.  
It is a practical migration utility that preserves already-entered schedule data while keeping the overall Molly architecture local-first.
