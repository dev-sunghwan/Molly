# Local Repository Cleanup

## Background

The local SQLite backend had already become the default execution path, but the runtime boundary still carried Google-shaped naming and structure such as `calendar_client` and `gcal_service`. That mismatch made the code harder to reason about and would have made the next integration steps unnecessarily messy.

## What Changed

- Added `calendar_repository.py` as Molly's backend-agnostic calendar execution boundary.
- Split the Google implementation into `google_calendar_backend.py`.
- Updated `bot.py` and `scheduler.py` to depend on `CalendarRepository` instead of a direct `gcal_service`.
- Kept `calendar_client.py` as a thin compatibility shim rather than removing it abruptly.

## Why This Matters

This was primarily a structural cleanup step, not a feature expansion step. Its value is that Telegram interpretation, reminders, and future assistant workflows now execute through a backend-neutral boundary, which makes local-first development much safer and easier to extend.

## Remaining Limits

- The local backend still does not support single-occurrence edit/delete for recurring events.
- Some older documents still describe `calendar_client.py` as the main runtime integration surface.

## Next Step

The next phase is wiring a real `OpenClaw Telegram provider`, so Molly can first try structured draft extraction from Telegram text and then fall back to heuristics when needed.
