# Molly Roadmap (English)

## 1. Purpose

Molly is a dedicated family scheduling assistant.

- Molly has its own Gmail account.
- Molly owns and manages separate Google Calendars for family members under that account.
- Family members do not directly grant Molly access to their personal email or personal calendars.
- Molly-managed calendars act as the family's scheduling system of record.

The goal is to evolve Molly from a command-driven Telegram bot into a practical family assistant that can understand natural language and email while updating calendars safely.

## 1.1 Current Priority

The current product priority is:

1. Improve natural-language scheduling through Telegram
2. Design and migrate toward a local SQLite-backed calendar backend
3. Stabilize clarification behavior for real daily use
4. Continue email work in parallel, but not ahead of Telegram usability

The near-term goal is to make Molly practically useful first as a Telegram scheduling assistant.
In parallel, Molly now needs a local-first path that reduces Google account risk.
The working MVP definition now follows [local_first_mvp_en.md](/home/sunghwan/projects/Molly/docs/local_first_mvp_en.md:1).

## 2. Current State Summary

Already implemented in the current codebase:

- Telegram bot operation
- Allowlist-based access control
- Local SQLite calendar backend as the default execution path
- Google Calendar adapter path retained
- SQLite-backed workflow state storage
- Event views: `today`, `tomorrow`, `week`, `month`, `next`, `upcoming`
- Event actions: `add`, `edit`, `delete`, `delete all`
- Search support
- APScheduler-based reminders, daily summary, and tomorrow preview
- Separate calendars per family member
- Basic parser and utility tests

Not implemented yet:

- Real OpenClaw provider integration
- Provider-agnostic email ingestion
- Schedule-candidate extraction from externally pasted notice text in Telegram
- Ambiguity handling and clarification dialogue
- Structured execution history and audit trail
- OpenClaw/Hermes integration boundaries

## 3. Core Operating Rules

The following rules remain in force:

- Final calendar mutations must be executed by deterministic Python logic.
- LLM/agent capabilities are limited to interpretation, summarization, candidate extraction, and ambiguity handling.
- LLMs must not call Google Calendar APIs directly.
- If the target calendar is not clear in an email or natural-language request, Molly must ask a follow-up question.
- If a person is explicitly mentioned, that person's Molly-managed calendar is the primary candidate.
- Ambiguous or destructive operations must not execute immediately without confirmation.
- Prefer incremental evolution over a full rewrite.

## 4. Recommended Architecture

Molly should evolve into the following layered structure.

### 4.1 Interface Layer

- Telegram input
- Gmail input
- Future summary/reminder/weather outputs

### 4.2 Understanding Layer

- Natural-language interpretation
- Email summarization
- Scheduling information extraction
- Production of a shared intent structure

Only this layer should use OpenClaw or other LLM/agent capabilities.

The recommended Telegram natural-language flow is:

- Telegram message
- OpenClaw/LLM extraction
- structured Telegram draft
- Python validation / normalization
- clarification decision
- Molly core execution
- Telegram response

In other words, OpenClaw acts as the interpreter and Molly core keeps final
calendar execution authority.

### 4.3 Decision Layer

- Decide which calendar to use
- Detect missing required fields
- Detect ambiguity
- Check conflict/duplication/risk conditions
- Decide whether Molly must ask a follow-up question

### 4.4 Execution Layer

- Local calendar read/write operations
- create/update/delete/search execution
- reminder scheduling support

This layer remains deterministic Python.

Google Calendar and Gmail should now be treated as optional adapters rather than the default backend.

### 4.5 State and Audit Layer

- Email processing state
- Pending clarification state
- Execution results
- Idempotency keys
- Change history
- Phase completion log

## 5. Technical Direction

### 5.1 Keep Deterministic in Python

- Date/time normalization
- Timezone handling
- Calendar selection rules
- Required-field validation
- create/update/delete execution
- Recurrence generation
- Conflict and duplicate checks
- Destructive-action safety rules
- State persistence and replay protection
- Scheduler and reminder logic

### 5.2 Delegate to Agent/LLM

- Natural-language understanding
- Email summarization
- Extraction of title/time/person/location
- First-pass relevance classification
- Ambiguity detection
- Drafting clarification questions
- Generating daily briefing language

Email handling uses a hybrid strategy.

- First choice: an LLM/OpenClaw layer produces a structured extraction draft
- Fallback: deterministic heuristic extraction
- Final decision and execution: Python validation plus Molly workflow

## 6. OpenClaw / Hermes Integration

### 6.1 OpenClaw

Use OpenClaw in the assistant interpretation layer.

- Telegram free text -> intent
- Email body -> schedule candidate
- Clarification question generation
- Summaries

It is not an immediate hard dependency.
First stabilize the Molly core and the shared intent schema, then connect OpenClaw through a clean adapter.

### 6.2 Hermes

Hermes is a good fit for event-driven workflow orchestration.

- New email processing
- Reminder triggers
- Morning summary
- Evening preview
- Weekly summary
- Weather-based daily briefing

Initially, keep the simple in-process Python scheduler and introduce Hermes when workflows become more complex.

## 6.3 External Adapter Rule

Google should remain an optional adapter even if it is reattached later.

- Prefer the local SQLite backend as the source of truth.
- Treat Google Calendar as an import/export or optional sync target.
- Treat Gmail as one possible provider among several future email adapters.

The transition rationale and migration outline are recorded in [local_first_transition_en.md](/home/sunghwan/projects/Molly/docs/local_first_transition_en.md:1).

## 6.4 Gmail Authentication Rule

Keep Gmail authentication separate from Calendar authentication.

- `credentials.json` can still reuse the same OAuth client.
- Calendar uses `token.json`.
- Gmail uses `gmail_token.json`.
- Future Gmail scope changes should only require refreshing the Gmail token path.

This keeps Gmail and Calendar permission lifecycles independent.

Run the initial Gmail authorization with:

```bash
./.venv/bin/python scripts/gmail_auth_check.py
```

To also print recent inbox messages after authorization:

```bash
./.venv/bin/python scripts/gmail_auth_check.py --list 5
```

## 7. Phased Implementation Plan

### Phase 0. Baseline Stabilization

Goal:

- Standardize the Python environment and runtime setup
- Start formal documentation
- Confirm current behavior still works

Status:

- Completed

Completion criteria:

- Virtual environment created
- Dependencies installed
- Baseline tests passing
- Telegram bot launch confirmed

### Phase 1. Intent Schema

Goal:

- Introduce a shared model that can represent both command-style and natural-language requests

Key work:

- Define `ScheduleIntent`
- Define `IntentResolution`
- Define `ExecutionResult`
- Design the bridge from current `commands.py` outputs

Completion criteria:

- Existing Telegram commands can be converted into the shared intent structure
- Calendar writes are separated from interpretation by an explicit validation boundary

### Phase 2. Clarification Flow

Goal:

- Make Molly ask follow-up questions when the target calendar or other critical fields are missing

Key work:

- Detect missing fields
- Generate follow-up questions
- Store pending clarification state
- Merge user replies back into the pending intent

Completion criteria:

- Requests without a clear target calendar do not execute immediately
- Molly can ask a follow-up question and continue after the answer

### Phase 3. State Storage

Goal:

- Introduce SQLite-backed state storage

Key work:

- Store pending clarification state
- Store processed email/message records
- Store execution audit records
- Store idempotency keys

Completion criteria:

- In-progress state survives restarts
- Duplicate emails/messages can be suppressed

### Phase 4. Gmail Ingestion

Goal:

- Start reading and processing scheduling-related emails from Molly's Gmail inbox

Key work:

- Add a Gmail adapter
- Fetch unread/new messages
- Normalize message bodies
- Build schedule candidates
- Mark processing state

Completion criteria:

- New emails can produce schedule candidates
- The same email is not processed repeatedly

### Phase 5. Assistant Workflow

Goal:

- Complete the flow from email/free text -> interpretation -> validation -> clarification -> execution -> report

Key work:

- candidate -> confirmed event pipeline
- Telegram execution report
- Ambiguity and failure branching

Completion criteria:

- Molly can safely add events from natural language or email

### Phase 6. OpenClaw Integration

Goal:

- Improve understanding quality for free text and email

Key work:

- OpenClaw adapter
- Structured extraction contract
- Deterministic parser fallback

Completion criteria:

- OpenClaw produces intent drafts and Python validates/executes them

### Phase 7. Hermes Integration

Goal:

- Expand event-driven automation

Key work:

- Email event workflow
- Reminder workflow
- Daily/weekly summary workflow
- Weather workflow

Completion criteria:

- High-frequency automation is stabilized through explicit workflows

## 8. Prioritized Task List

Proceed in this order:

1. Maintain bilingual roadmap documents and a phase log
2. Design the intent schema
3. Implement the clarification flow
4. Introduce SQLite state storage
5. Add the Gmail adapter
6. Implement email-to-candidate processing
7. Add the OpenClaw adapter
8. Add Hermes workflows
9. Add weather/context briefing

## 9. Logging Rule

Whenever a phase is completed, record it in `docs/phase_log.md`.

Each log entry should include:

- Completion date
- Phase name
- Goal
- What was actually completed
- Remaining risks
- Next phase

Keep entries short and factual.
