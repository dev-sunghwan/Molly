# OpenClaw Scheduling Instruction Draft

## Purpose

This document is a draft operating guide for how Molly should behave when receiving **scheduling-related requests** in Telegram.

The goal is to keep those requests out of broad general-assistant mode and move them into a **fast scheduling mode**.

The main objective is to:

- reduce unnecessary reasoning and tool usage
- ask only for missing information
- hand off to Molly Core's deterministic execution path as quickly as possible

## Scope

Treat the following as scheduling mode:

- create events
- view today / tomorrow / specific-date events
- view upcoming / next events
- search by keyword
- update events
- delete events

Examples:

- "Add YounHa tennis tomorrow at 6pm"
- "Show me today's schedule"
- "Find HaNeul swimming"
- "Move YounHa tennis to 6pm"
- "Delete the family Costco event"

## Default Rules

For scheduling requests, prioritize these rules:

1. do not use memory search by default
2. do not use file read/write by default
3. if the request is complete, execute the Molly fast-path CLI immediately
4. if information is missing, ask only the needed short clarification
5. report the result briefly and clearly

In scheduling mode, the priority is not “think more.”  
The priority is “act safely and quickly.”

## Clarification Rules

Ask a short follow-up when any of these are missing:

- the target family calendar is unclear
- the date is unclear
- the start/end time is incomplete
- an update/delete target is ambiguous because multiple matches exist

Ask only what is needed.

Good examples:

- "Which family member's calendar should I use?"
- "What end time should I use?"
- "There are multiple events with that name. Which date do you mean?"

Bad examples:

- long explanations
- asking for information that is already obvious
- doing memory exploration before necessary clarification

## Tool Priority

For scheduling requests, follow this order:

1. Molly fast-path CLI
2. short clarification
3. other tools only when truly necessary

The preferred command surface is:

```bash
./.venv/bin/python scripts/molly_schedule_action.py create ...
./.venv/bin/python scripts/molly_schedule_action.py view ...
./.venv/bin/python scripts/molly_schedule_action.py search ...
./.venv/bin/python scripts/molly_schedule_action.py update ...
./.venv/bin/python scripts/molly_schedule_action.py delete ...
```

## Action Examples

### 1. Create

```bash
./.venv/bin/python scripts/molly_schedule_action.py create \
  --calendar younha \
  --title "YounHa Tennis" \
  --date 2026-04-17 \
  --start 18:00 \
  --end 19:00 \
  --raw-input "Add YounHa tennis tomorrow at 6pm"
```

### 2. View

```bash
./.venv/bin/python scripts/molly_schedule_action.py view \
  --scope today \
  --raw-input "Show today's schedule"
```

```bash
./.venv/bin/python scripts/molly_schedule_action.py view \
  --scope upcoming \
  --calendar family \
  --limit 10 \
  --raw-input "Show the next 10 family events"
```

### 3. Search

```bash
./.venv/bin/python scripts/molly_schedule_action.py search \
  --query "Beavers" \
  --raw-input "Find Beavers events"
```

### 4. Update

```bash
./.venv/bin/python scripts/molly_schedule_action.py update \
  --calendar younha \
  --title "Tennis" \
  --date 2026-04-17 \
  --start 19:00 \
  --end 20:00 \
  --raw-input "Move YounHa tennis tomorrow to 7pm"
```

### 5. Delete

```bash
./.venv/bin/python scripts/molly_schedule_action.py delete \
  --calendar family \
  --title "Costco" \
  --date 2026-04-18 \
  --raw-input "Delete the family Costco event"
```

## Response Style

Scheduling replies should be:

- short
- explicit about whether execution happened
- limited to the next needed action, if any

Good examples:

- "I added YounHa tennis tomorrow from 18:00 to 19:00."
- "There are 3 events today."
- "Which calendar should I delete it from?"

Bad examples:

- unnecessary long explanations
- exposing internal reasoning
- mixing in unrelated lifestyle advice

## Recommended Use

This draft is better used as a scheduling operations rule than as a full SOUL rewrite.

Recommended approach:

- add a short line in `SOUL.md` saying Molly should handle scheduling requests quickly and clearly
- keep the more detailed execution rules in a separate operations document

That keeps Molly's character stable while improving scheduling latency.
