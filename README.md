# Molly

Molly is a personal family scheduling assistant that I built for day-to-day use at home. It connects Telegram, Google Calendar, Gmail, and OpenClaw so family schedule requests can be captured, clarified, and turned into calendar actions with less manual coordination.

The project is already used in real life, but it is still an actively evolving personal system rather than a polished product. The current codebase works, while the architecture and workflow boundaries still need more cleanup as the feature set has grown.

## Why I built it

Family schedules are scattered across chat messages, emails, and multiple calendars. Molly started as a lightweight Telegram bot for checking and adding events, then grew into a broader assistant that can:

- read and update multiple family calendars
- handle natural-language-like Telegram requests
- send daily summaries and event reminders
- turn schedule-related Gmail messages into candidate events
- use OpenClaw as an extraction layer while keeping final execution deterministic in Python

## Current capabilities

- Telegram-based schedule lookup and event creation
- support for multiple family calendars and per-user reminder subscriptions
- recurring-event, multi-day-event, edit, move, and delete flows
- morning summaries, evening previews, and per-event reminders
- Gmail ingestion with allowlisted senders and clarification workflow
- OpenClaw bridge for structured `create_event` extraction
- local-first runtime with file-backed state and test coverage around the core workflows

## How it works

Molly keeps Google Calendar as the system of record. Telegram and Gmail act as input channels, and the Python core resolves each request before executing it against the configured calendar backend.

```text
Telegram / Gmail / OpenClaw
          |
          v
 intent extraction and clarification
          |
          v
       Molly Core
          |
          v
   Google Calendar backend
```

Important modules:

- `bot.py` - Telegram runtime and message dispatch
- `molly_core.py` - deterministic execution layer
- `calendar_repository.py` - backend abstraction for calendar operations
- `scheduler.py` - summaries and reminders
- `assistant_workflow.py` - Gmail-driven candidate flow
- `openclaw_molly_bridge.py` - OpenClaw integration boundary

## Project status

Molly is in active personal use and has moved well beyond its original MVP. The next work is less about adding basic features and more about improving maintainability:

- simplify boundaries between deterministic parsing and extraction layers
- reduce growth in cross-module coupling
- make the runtime easier to operate and inspect
- tighten documentation around current architecture instead of the original plan only

## Tech stack

- Python 3.10+
- `python-telegram-bot`
- Google Calendar API
- Gmail API
- APScheduler
- OpenClaw integration
- Pytest and Ruff for local quality checks

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

The app requires local configuration for Telegram, calendar credentials, and the selected calendar backend. Secret files and tokens should stay outside version control.

## Documentation

- `implementation_plan.md` records the original project plan and early design decisions.
- The current code has since grown past that initial plan, so this README describes the present project direction.
