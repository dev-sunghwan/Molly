# OpenClaw-Centered Molly Architecture

## 1. Why This Direction Was Chosen

The real goal of Molly is not a specific Telegram bot implementation. The goal is to combine two things reliably:

- natural-language conversation and ambiguity handling
- safe schedule execution

From that perspective, the Telegram bot itself is only a UI channel.

What matters is not primarily:

- which bot account is used
- which process receives the message first

but rather:

- who interprets the user's natural language
- who performs the final schedule mutation

Under that framing, the Molly system is best split into:

- OpenClaw: conversational interpreter and clarification layer
- Molly Core: deterministic execution engine
- Local calendar DB: system of record

## 2. Target Architecture

The recommended structure is:

`User -> OpenClaw-connected Telegram bot -> OpenClaw -> Molly Core -> Local calendar DB`

In this structure, OpenClaw talks directly to the user.

It is responsible for:

- understanding natural-language requests
- asking follow-up questions when fields are missing
- resolving ambiguous dates, times, and target calendars
- producing a structured execution request

Molly Core then accepts only the structured request and executes it.

It is responsible for:

- request schema validation
- date/time normalization
- conflict checks
- event creation/update/deletion
- logging

## 3. Separation of Responsibilities

### 3.1 What OpenClaw Owns

- Telegram-facing conversation
- natural-language interpretation
- collecting missing information
- clarification questions
- converting user intent into a structured draft/request
- presenting results back in natural language

### 3.2 What Molly Core Owns

- calendar actions such as create/view/update/delete/search
- local DB reads and writes
- validation and normalization
- recurring rule handling
- reminder/summary data support
- audit/logging

## 4. The Key Principle

In this structure, the LLM is not the executor.

The LLM:

- interprets
- asks
- organizes

But it does not directly mutate the calendar database.

All real write operations stay inside Molly Core.

This boundary must remain clear:

- OpenClaw: interpretation boundary
- Molly Core: execution boundary

That separation reduces the risk of:

- incorrect event creation due to LLM misunderstanding
- overconfident execution on ambiguous dates
- wrong target-calendar inference
- schedule changes made without deterministic checks

## 5. Why This Fits Better Than a Molly-Bot-Centered Design

The older direction kept Molly bot as the primary entry point and tried to add heuristic or provider-backed NLU inside that runtime.

That can work, but over time it creates some pressure:

- clarification UX becomes tightly coupled to bot implementation details
- the bot runtime grows as LLM handling expands
- the "family assistant" experience gets split between the bot layer and the NLU adapter layer

By contrast, an OpenClaw-centered structure has several advantages:

- conversational UX stays where it naturally belongs
- Molly Core can become a smaller, more stable execution engine
- the structure remains consistent if input channels expand beyond Telegram
- outside notices, summaries, and follow-up questions can live in the same conversation layer

## 6. The Constraint We Actually Confirmed

In an earlier attempt, Molly tried to call OpenClaw as if it exposed a direct OpenAI-compatible HTTP inference endpoint. That is not what was actually confirmed in the current local setup.

What was confirmed:

- the local OpenClaw gateway/control UI is running
- but `/v1/chat/completions` was not found
- the runtime appears more CLI/gateway/agent oriented than raw HTTP inference server oriented

This does not mean OpenClaw cannot be used.

It means the integration path is probably not `direct HTTP inference call` from Molly.

## 7. Practical Integration Options

### Option A. CLI Adapter

Use OpenClaw's CLI surface as the interpretation layer callable from Molly or from an integration bridge.

Examples:

- `openclaw infer model run ...`
- or a later agent/capability command

Pros:

- best fit with the currently confirmed surfaces
- fastest path to an MVP
- lower implementation complexity

Cons:

- requires subprocess and output parsing
- less elegant than a deeper tool/MCP integration

### Option B. OpenClaw Tool / Capability Integration

Expose Molly Core functions so OpenClaw can call them as tools.

Pros:

- most natural long-term structure
- aligns well with the OpenClaw-centered architecture

Cons:

- higher upfront integration cost
- requires more understanding of OpenClaw's extension surface

### Option C. Local HTTP Bridge

Run Molly Core as a localhost API and let OpenClaw call it.

Pros:

- very explicit service boundary

Cons:

- adds another long-running service
- likely too heavy for the current stage

## 8. Recommended Implementation Sequence

The most practical first implementation path is:

### Step 1. Normalize Molly Core's execution interface

Prepare one structured execution entry point for actions such as:

- `create_event`
- `view_daily`
- `view_range`
- `update_event`
- `delete_event`

### Step 2. Choose the first adapter OpenClaw will use

For the first version, a CLI adapter is the recommended option.

That means OpenClaw should eventually produce a structured request such as:

```json
{
  "action": "create_event",
  "target_calendar": "younha",
  "title": "Tennis",
  "target_date": "2026-04-16",
  "start_time": "17:00",
  "end_time": "18:00",
  "all_day": false
}
```

Molly Core should then execute only that structured request.

### Step 3. Connect only one end-to-end use case first

Start with `create_event` only.

Keep the first slice narrow:

- Telegram conversation
- clarification
- structured request generation
- Molly Core execution
- user-facing result

After that is stable, extend to view/update/delete.

## 9. Design Principles

- the Telegram bot is a replaceable UI
- OpenClaw is the assistant/controller
- Molly Core is the executor
- the local calendar DB is the source of truth
- the LLM is used for interpretation only
- validation and execution remain deterministic Python logic

## 10. Current Conclusion

The architecture direction is now clear.

Molly should no longer be thought of primarily as "a Telegram bot with embedded NLU."

It should be treated as:

`OpenClaw handles conversation, Molly Core handles execution`

The next implementation phase is to build the first execution interface that makes this architecture real.
