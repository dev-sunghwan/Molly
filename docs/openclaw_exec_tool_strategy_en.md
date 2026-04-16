# OpenClaw Exec Tool Strategy

## Why The Direction Was Adjusted

After inspecting the real OpenClaw Telegram session log, it became clear that OpenClaw already uses the following tools naturally inside conversation:

- `memory_search`
- `read`
- `write`
- `exec`

By contrast, the one-shot `openclaw infer ...` and `openclaw agent ...` calls attempted from the local shell have not been returning reliably in the current environment.

That means the more trustworthy execution surface right now is not a guessed inference CLI path, but the `exec` tool that OpenClaw is already using successfully in real Telegram conversations.

## Strategy

The first practical Molly integration path is therefore:

`Telegram -> OpenClaw conversation -> OpenClaw exec tool -> Molly Core CLI -> Local calendar DB`

In this structure, OpenClaw:

1. understands the user's request
2. asks clarification questions if needed
3. completes the structured request
4. calls Molly Core through the `exec` tool

## What Was Added

To match OpenClaw's `exec` tool usage, a shell-friendly argv-based executor was added:

- `scripts/molly_create_event.py`

Instead of reading stdin JSON, this script accepts explicit command-line flags.

Example:

```bash
./.venv/bin/python scripts/molly_create_event.py \
  --calendar younha \
  --title "Tennis" \
  --date 2026-04-16 \
  --start 17:00 \
  --end 18:00 \
  --raw-input "Add YounHa tennis tomorrow at 5pm"
```

## Why This Helps

- it is easier for OpenClaw's `exec` tool to call
- it is easier to debug than heredoc/stdin JSON
- the schedule mutation command is explicit and inspectable
- Molly Core's deterministic validation remains unchanged

## Expected OpenClaw Behavior

OpenClaw should first complete the structured scheduling request internally, then build a command like:

```bash
./.venv/bin/python scripts/molly_create_event.py \
  --calendar younha \
  --title "Tennis" \
  --date 2026-04-16 \
  --start 18:30 \
  --end 20:00 \
  --raw-input "Add YounHa tennis tomorrow from 6:30pm to 8pm"
```

The execution result is returned as JSON.

## Current Conclusion

The first realistic live Molly path should not be treated as a fixed `infer model run` integration. It is more practical to use the `exec` tool surface that OpenClaw is already using successfully in actual Telegram conversations.

The next step is to teach OpenClaw to follow this execution pattern and validate one real end-to-end event creation flow from the Saekomm conversation.

## Python Environment Rule

After re-checking the live Saekomm conversation log, OpenClaw had correctly built the Molly execution command, but it used the system `python3`:

```bash
python3 /home/sunghwan/projects/Molly/scripts/molly_create_event.py ...
```

That failed with:

```text
ModuleNotFoundError: No module named 'dotenv'
```

The cause was not a missing Molly dependency. The cause was the wrong interpreter.

- `pyproject.toml` already declares `python-dotenv`
- Molly's `.venv` already has `python-dotenv` installed
- the system `python3` is not the intended Molly runtime environment

So whenever OpenClaw calls Molly, it must use the project's virtualenv Python.

The preferred command is one of these:

```bash
/home/sunghwan/projects/Molly/.venv/bin/python /home/sunghwan/projects/Molly/scripts/molly_create_event.py ...
```

Or, when the working directory is the Molly project root:

```bash
./.venv/bin/python scripts/molly_create_event.py ...
```

This is now a required execution rule for live integration. Further Saekomm validation should be retried only with the `.venv`-based command path.
