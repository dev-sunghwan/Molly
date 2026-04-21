# OpenClaw Scheduling Fast Path

## Goal

For scheduling requests, OpenClaw should avoid broad general-assistant behavior and move into Molly Core's deterministic execution path as quickly as possible.

The target path is:

`Telegram -> OpenClaw scheduling mode -> Molly fast-path CLI -> Molly Core -> Local calendar DB`

## Why This Is Needed

The older Python Molly bot was fast but limited in expression.  
The current OpenClaw-centered structure is more flexible, but scheduling requests can become slower if OpenClaw uses broad tools such as memory search or file reads before acting.

Scheduling should therefore use a dedicated fast path.

## Principles

For scheduling requests, OpenClaw should:

1. structure the schedule intent
2. call the Molly fast-path CLI immediately when information is complete
3. ask short clarification questions only when required
4. avoid unnecessary memory/file tool usage

## Fast-Path CLI

- `scripts/molly_schedule_action.py create`
- `scripts/molly_schedule_action.py view`
- `scripts/molly_schedule_action.py search`
- `scripts/molly_schedule_action.py delete`
- `scripts/molly_schedule_action.py update`

This gives OpenClaw an explicit argv-style execution surface instead of forcing longer stdin JSON assembly.

## Draft OpenClaw Scheduling Guidance

When handling scheduling requests, prioritize these rules:

- do not use memory search by default
- do not use file read/write by default
- if the request is complete, execute the Molly CLI immediately
- if information is missing, ask only the minimum short clarification question
- report the final execution result in concise natural language

## Expected Outcome

- faster scheduling responses
- less OpenClaw reasoning overhead
- preserved Molly Core deterministic safety
- cleaner separation between general conversation and schedule execution
