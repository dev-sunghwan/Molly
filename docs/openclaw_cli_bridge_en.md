# OpenClaw CLI Bridge For Create Event

## Goal

The goal of this phase is to create the first real execution bridge that can carry a `create_event` request interpreted by OpenClaw into Molly Core's deterministic execution layer.

## Current Scope

This bridge intentionally keeps the scope narrow.

- action: `create_event`
- input: one Telegram natural-language message
- OpenClaw output: structured JSON request
- Molly Core input: structured JSON request
- final execution: local calendar DB mutation

In other words, this phase builds the first real execution pipe between OpenClaw and Molly Core.

## Added Components

- `openclaw_molly_bridge.py`
  - builds the OpenClaw extraction prompt
  - parses OpenClaw JSON output
  - invokes Molly Core's CLI executor
- `scripts/openclaw_create_event_bridge.py`
  - one-shot entrypoint for running the bridge on a single message
- `tests/test_openclaw_molly_bridge.py`
  - verifies execution and clarification paths

## Current Flow

The bridge now follows this shape:

`message text -> OpenClaw inference -> structured JSON -> Molly Core CLI -> execution result`

An example of the structured request expected from OpenClaw is:

```json
{
  "action": "create_event",
  "target_calendar": "younha",
  "title": "Tennis",
  "target_date": "2026-04-16",
  "start_time": "17:00",
  "end_time": "18:00",
  "all_day": false,
  "raw_input": "Add YounHa tennis tomorrow at 5pm",
  "nlu": "openclaw",
  "request_source": "openclaw_cli_bridge"
}
```

When the request is incomplete, the bridge expects a clarification response instead of an execution request.

Example:

```json
{
  "status": "needs_clarification",
  "reason": "target_calendar is missing"
}
```

## Important Note

This bridge is not yet the final, fully locked-down OpenClaw invocation layer.

The local OpenClaw runtime surface has been partially confirmed, but the exact `model run` argument shape still needs final verification. For that reason, the current implementation keeps:

- the OpenClaw invocation layer
- the Molly Core execution layer

cleanly separated, so the command shape can be adjusted in one place.

## Why This Matters

Molly no longer needs to keep execution logic tied to a Telegram bot runtime.

No matter how OpenClaw eventually produces the structured JSON request, Molly Core can now consume the same execution surface.

That means the next iteration can focus on either:

- finalizing the real OpenClaw CLI invocation
- or switching later to a tool/capability integration

without forcing major changes in Molly Core.

## Next Step

The next step is to finalize the actual `infer/model run` invocation against the local OpenClaw runtime and prove one real end-to-end `create_event` flow from OpenClaw conversation to Molly Core execution.
