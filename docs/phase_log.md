# Molly Phase Log

This file records phase-level milestones as they are completed.

## Entry Format

Use the following structure for each completed phase.

### YYYY-MM-DD - Phase Name

- Goal:
- Completed:
- Risks:
- Next:

## Entries

### 2026-04-14 - Phase 0 Baseline Stabilization

- Goal: Standardize the local Python environment, confirm the current Telegram bot runtime, and establish project planning documents.
- Completed: Added `pyproject.toml`, created a project virtual environment, installed runtime and dev dependencies, created `.env`, restored `credentials.json`, completed Google OAuth to generate `token.json`, confirmed Telegram bot startup, and added bilingual roadmap documents plus this phase log.
- Risks: The codebase still mixes parsing, execution, and interface concerns; there is no shared intent schema or durable workflow state yet.
- Next: Phase 1 - Intent Schema

### 2026-04-14 - Phase 1 Intent Schema

- Goal: Introduce a shared intent model so existing Telegram command parsing can converge into a common execution boundary before future natural-language and email flows are added.
- Completed: Added `intent_models.py` for shared intent and execution dataclasses, added `intent_adapter.py` to translate existing command dicts into `ScheduleIntent` and `IntentResolution`, created an explicit READY / NEEDS_CLARIFICATION / INVALID boundary between interpretation and execution, added intent translation tests, updated project metadata, and verified the new layer with `80 passed` across parser, utility, and intent tests.
- Risks: The bot runtime still dispatches directly from command dicts instead of executing through the new intent boundary, and clarification/state persistence is not implemented yet.
- Next: Phase 2 - Clarification Flow

### 2026-04-14 - Phase 2 Clarification Flow

- Goal: Ensure Molly does not execute incomplete scheduling requests immediately and can ask a follow-up question when the target calendar is missing.
- Completed: Added `clarification_state.py` for in-memory pending clarification tracking, added fallback intent inference for `add ...` requests missing the calendar, connected the Telegram bot handler to the new intent resolution path, made Molly ask which family calendar to use when needed, and enabled follow-up replies containing a calendar name to resume execution. Added clarification tests and verified the updated parser/intent flow with `83 passed`.
- Risks: Pending clarification state is still in memory only, so it is lost on restart; clarification currently covers the missing target calendar path and not broader ambiguity classes yet.
- Next: Phase 3 - State Storage

### 2026-04-14 - Phase 3 State Storage

- Goal: Introduce SQLite-backed workflow state so Molly can manage multi-step assistant flows through an explicit storage boundary instead of relying only on in-memory process state.
- Completed: Added `state_store.py`, introduced a SQLite database at `data/molly_state.db`, persisted pending clarification state, added a minimal execution log table, migrated `clarification_state.py` from in-memory storage to SQLite-backed storage, initialized the database during bot startup, and recorded deterministic execution results from the intent execution path. Added storage tests and verified the updated stack with `86 passed`.
- Risks: The execution log is minimal and does not yet capture full user/message identifiers; processed email/message deduplication and richer audit fields are still future work.
- Next: Phase 4 - Gmail Ingestion

### 2026-04-14 - Phase 4 Gmail Ingestion

- Goal: Add a safe Gmail ingestion entry point so Molly can read and normalize inbox messages while tracking which external inputs have already been seen.
- Completed: Added `gmail_adapter.py` with list/fetch/normalize helpers for Gmail messages, implemented plain-text-first body extraction for multipart messages, extended `state_store.py` with `processed_inputs` tracking for future Gmail deduplication, added Gmail normalization tests, added processed-input storage tests, and verified the updated stack with `89 passed`. Later, added `gmail_client.py` with separate Gmail OAuth state using `gmail_token.json` while keeping the existing Calendar token isolated, added `scripts/gmail_auth_check.py` as a first-run authorization helper, and reverified the stack with `92 passed`.
- Risks: Gmail ingestion is not yet wired into a live polling or workflow loop, and the current adapter focuses on message normalization rather than schedule-intent extraction. Later live verification confirmed that `molly.kim.agent@gmail.com` can authenticate and list inbox messages successfully once the Gmail API is enabled.
- Next: Phase 5 - Assistant Workflow

### 2026-04-15 - Phase 5 Assistant Workflow

- Goal: Turn normalized Gmail messages into Molly workflow candidates and intent states so email input can enter the same assistant pipeline as Telegram input.
- Completed: Added `assistant_workflow.py` to classify Gmail messages into `ready`, `needs_clarification`, or `ignored` candidates using deterministic rules; connected those candidates to `ScheduleIntent` / `IntentResolution`; added tests for ready, clarification, and ignore paths; and reverified the overall stack with `95 passed`.
- Risks: The assistant workflow currently builds candidates from deterministic email heuristics only and is not yet wired to a live inbox processing loop or Telegram reporting path; automatic execution from email is still intentionally deferred.
- Next: Phase 6 - Inbox Processing Loop

### 2026-04-15 - Phase 6 Inbox Processing Loop

- Goal: Add a conservative inbox processing loop that can scan recent Gmail messages, skip already-seen inputs, classify new messages through the assistant workflow, and record their status.
- Completed: Added `inbox_processor.py` with one-shot recent inbox processing, duplicate skipping through `processed_inputs`, candidate status recording for new Gmail messages, and a compact processing report formatter. Added `scripts/process_inbox_once.py` as a runnable entrypoint and verified the updated stack with `98 passed`.
- Risks: This is currently a one-shot runner rather than a continuously scheduled Gmail worker, and it records candidate status without yet sending Telegram reports or automatically executing ready email-derived events.
- Next: Phase 7 - Telegram Reporting And Review Flow

### 2026-04-15 - Phase 7 Hybrid Email Extraction Layer

- Goal: Prepare Molly to use LLM/OpenClaw-style email understanding without giving up deterministic fallback and validation.
- Completed: Added `email_extraction.py` to define a structured extraction draft contract, updated `assistant_workflow.py` to prefer a supplied extraction draft and fall back to deterministic heuristics otherwise, added tests for the draft-driven ready/ignored paths, documented the hybrid strategy in the roadmap, and reverified the stack with `100 passed`.
- Risks: A real LLM/OpenClaw provider is not yet connected, so live email extraction still uses heuristics unless a structured draft is injected by another layer.
- Next: Phase 8 - Telegram Reporting And Review Flow

### 2026-04-15 - Priority Shift

- Goal: Reprioritize Molly toward day-to-day Telegram scheduling usability before pushing email automation further.
- Completed: Recorded the decision to treat Telegram natural-language scheduling as the primary near-term product goal, with email remaining an important parallel track rather than the lead track.
- Risks: The roadmap now has foundational email work ahead of Telegram natural-language work, so the next implementation phase should follow the updated priority rather than the previous numbering alone.
- Next: Telegram Natural-Language Scheduling

### 2026-04-15 - Telegram Natural-Language Scheduling

- Goal: Make Molly practically usable for day-to-day scheduling through Telegram without requiring rigid command syntax for common cases.
- Completed: Added `telegram_nlu.py` with a first practical Telegram natural-language path for common Korean/English schedule views and event creation requests, wired the bot to try this path after command parsing fails, extended clarification handling to accept date follow-up replies, added tests for Korean free-text scheduling and clarification behavior, and reverified the stack with `105 passed`.
- Risks: This is still a lightweight heuristic interpreter rather than full free-form language understanding; broader phrasing coverage, richer date expressions, and true LLM/OpenClaw-backed Telegram understanding are still future work.
- Next: Telegram Hybrid Extraction Layer

### 2026-04-15 - Telegram Hybrid Extraction Layer

- Goal: Reshape Telegram scheduling into the same hybrid pattern as email so Molly can accept structured OpenClaw/LLM drafts first while preserving deterministic validation and heuristic fallback.
- Completed: Added `telegram_extraction.py` for a structured Telegram draft contract and extraction prompt helper, added `telegram_extractor_provider.py` as the runtime provider hook, updated `telegram_nlu.py` to accept a supplied draft before falling back to heuristics, wired `bot.py` to pull an optional `telegram_extractor` from application state, added tests for draft-driven create/view/clarification paths, and documented the Telegram flow explicitly in the bilingual roadmaps.
- Risks: A real OpenClaw provider is still not registered in the running bot, so live Telegram traffic still uses heuristics unless an extractor is injected at startup. View actions from drafts currently cover daily/range patterns but not the full command surface.
- Next: Real OpenClaw Telegram Provider

### 2026-04-15 - Local-First Strategy Shift

- Goal: Record the architectural direction change triggered by Google account suspension risk and reframe Molly around a local-first calendar backend.
- Completed: Added dedicated transition records in `docs/local_first_transition_ko.md` and `docs/local_first_transition_en.md`, updated the bilingual roadmaps to treat a local SQLite calendar backend as the new target source of truth, and explicitly demoted Google Calendar/Gmail to optional adapters rather than mandatory backends.
- Risks: The codebase still executes against Google Calendar today, so the strategic shift is documented but not yet implemented as the default backend. Event import, local schema, and adapter boundaries still need to be built.
- Next: Local Calendar Schema And Backend Interface

### 2026-04-15 - Local Calendar Backend Foundation

- Goal: Turn the local-first strategy into a working default execution path by introducing a SQLite-backed calendar backend behind Molly's existing execution boundary.
- Completed: Added `local_calendar_backend.py` with local SQLite storage for calendars and events, recurring weekly event expansion, search/upcoming listing, and non-recurring edit/delete flows. Updated `calendar_client.py` into a backend facade that routes to the local provider when `MOLLY_CALENDAR_BACKEND=local`, relaxed `config.validate()` so Google credentials are only required for the Google backend, switched the bot startup flow to authenticate against the configured calendar backend, added local backend tests, and reverified the stack with `111 passed`.
- Risks: The local backend does not yet support single-occurrence edits/deletes for recurring events, and Google event import/sync is still future work. Scheduler internals still use legacy naming (`gcal_service`) even though the backend is no longer Google-specific by default.
- Next: Local Repository Interface Cleanup

### 2026-04-15 - Local-First MVP Definition

- Goal: Freeze the near-term Molly product scope so implementation can follow a clear local-first family-assistant target instead of drifting toward a general calendar platform.
- Completed: Added `docs/local_first_mvp_ko.md` and `docs/local_first_mvp_en.md` to define the MVP, clarified that Molly's core experience is Telegram-first schedule management plus convenient external notice intake, explicitly deprioritized broad calendar-platform features and Gmail-first automation, and linked the MVP documents from the transition records and bilingual roadmaps.
- Risks: The MVP is now clearer, but the implementation still needs the next concrete phases: backend cleanup, real OpenClaw provider integration, and Telegram notice-intake workflows.
- Next: Local Repository Interface Cleanup
