# Reminder Worker Split

## Why It Was Needed

In the older Molly runtime, `bot.py` handled two responsibilities at once:

- receiving Telegram messages
- running the scheduler for reminders, daily summaries, and tomorrow previews

The current target direction is:

`Telegram -> OpenClaw -> Molly Core -> Local Calendar DB`

In that structure, `bot.py` no longer needs to stay running as the main front-end process. If the scheduler is only started inside `bot.py`, reminder functionality disappears even though the reminder logic still exists.

So the issue was not that reminders had been removed. The issue was that the old process responsible for starting them was no longer part of the new live path.

## What Was Added

A new entrypoint was added:

- `scripts/run_reminder_worker.py`

This worker:

1. validates config and initializes state storage
2. connects to the configured calendar backend
3. creates a Telegram `Bot` instance
4. starts the existing jobs from `scheduler.py`
5. stays alive as an independent process

## Current Structure

Responsibilities now split more cleanly:

- OpenClaw / Saekomm: conversation, natural-language understanding, clarification
- Molly Core: deterministic schedule execution
- Reminder Worker: reminders, daily summaries, and tomorrow previews

That means `bot.py` is no longer required as the always-on runtime for reminders.

## How To Run It

Long-running mode:

```bash
./.venv/bin/python scripts/run_reminder_worker.py
```

Startup check only:

```bash
./.venv/bin/python scripts/run_reminder_worker.py --startup-check
```

## Why This Matters

This is not just a convenience script. It is the correct responsibility split for the new architecture.

- the conversational UI and background jobs are separated
- reminder delivery no longer depends on the legacy Molly polling bot
- Molly Core remains the deterministic execution layer
- the worker can later be managed independently with systemd, tmux, supervisor, or a similar runtime
