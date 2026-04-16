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

### 2026-04-15 - Local Repository Interface Cleanup

- Goal: Replace the remaining Google-shaped runtime boundary with a backend-agnostic repository interface so the local-first architecture is reflected in the execution path, not just the storage layer.
- Completed: Added `calendar_repository.py` as the new backend-agnostic execution boundary, split the Google implementation into `google_calendar_backend.py`, reduced `calendar_client.py` to a compatibility shim, updated `bot.py` and `scheduler.py` to depend on a `CalendarRepository` instance instead of a `gcal_service`, kept formatting helpers centralized outside the backend modules, and recorded the rationale in `docs/local_repository_cleanup_ko.md` and `docs/local_repository_cleanup_en.md`.
- Risks: `calendar_client.py` still exists as a compatibility layer and some historical docs still describe it as the main integration surface. Google and local backends are now cleaner to swap, but recurring single-occurrence edit/delete limitations in the local backend remain unchanged.
- Next: Real OpenClaw Telegram Provider

### 2026-04-15 - Real OpenClaw Telegram Provider

- Goal: Connect the existing Telegram extraction hook to a real provider path so Molly can use local LLM assistance for interpretation while preserving deterministic execution and safe fallback behavior.
- Completed: Added `openclaw_telegram_provider.py` for OpenAI-compatible local endpoint calls, JSON parsing, and `ExtractedTelegramDraft` conversion; updated `telegram_extractor_provider.py` to build the configured extractor; extended `config.py` with extractor backend and OpenClaw settings; updated `bot.py` to register the extractor at startup; added provider tests; and documented the integration in `docs/openclaw_telegram_provider_ko.md` and `docs/openclaw_telegram_provider_en.md`.
- Risks: The integration path is ready, but a real local endpoint URL and model still need to be configured in `.env` before Molly can use OpenClaw live. Fallback to heuristics remains important because local model output quality can still vary by prompt and model choice.
- Next: OpenClaw Runtime Configuration And Live Telegram Validation

### 2026-04-15 - OpenClaw-Centered Architecture Decision

- Goal: Resolve the remaining architecture ambiguity around Telegram, OpenClaw, and Molly Core by documenting the target responsibility split and choosing a practical integration direction.
- Completed: Confirmed that the long-term design should treat the Telegram bot as replaceable UI, OpenClaw as the conversational interpretation layer, and Molly Core as the deterministic execution engine backed by the local calendar DB. Documented the target structure and integration options in `docs/openclaw_centered_architecture_ko.md` and `docs/openclaw_centered_architecture_en.md`, including the conclusion that direct OpenAI-style HTTP inference was the wrong assumption for the current local OpenClaw runtime and that a CLI/tool-oriented integration path is the more practical next step.
- Risks: The architecture decision is now clear, but the actual OpenClaw-to-Molly execution bridge has not yet been implemented. The first bridge should stay narrow and prove one end-to-end action before broader migration away from the existing Molly bot runtime.
- Next: Molly Core Execution Interface

### 2026-04-15 - Molly Core Execution Interface

- Goal: Extract Molly's deterministic execution logic into a reusable core interface that can be called from Telegram today and from an OpenClaw bridge next.
- Completed: Added `molly_core.py` as the reusable execution boundary around the calendar repository, moved bot-side execution through `MollyCore`, added `molly_core_requests.py` to parse structured bridge requests into internal intents, added `scripts/molly_core_execute.py` as the first CLI execution entrypoint for structured requests, registered the new modules in `pyproject.toml`, and added focused tests for request parsing and `create_event` execution.
- Risks: The structured request interface currently supports only the first narrow bridge action (`create_event`). OpenClaw is not yet calling this CLI entrypoint, so the conversation layer and execution layer are now separated but not yet wired end-to-end.
- Next: OpenClaw CLI Bridge For Create Event

### 2026-04-15 - OpenClaw CLI Bridge For Create Event

- Goal: Build the first narrow bridge layer that can take an OpenClaw-produced `create_event` request and route it into Molly Core's deterministic CLI executor.
- Completed: Added `openclaw_molly_bridge.py` to define the first OpenClaw-to-Molly bridge flow, including a create-event extraction prompt, JSON parsing, and Molly Core CLI execution handoff. Added `scripts/openclaw_create_event_bridge.py` as a runnable one-shot bridge entrypoint, added focused bridge tests, registered the new module in `pyproject.toml`, and documented the bridge design in `docs/openclaw_cli_bridge_ko.md` and `docs/openclaw_cli_bridge_en.md`.
- Risks: The bridge flow is now implemented, but the exact local OpenClaw `infer model run` argument shape still needs one final runtime verification. The current adapter isolates that uncertainty in a single command builder, but a real end-to-end live invocation is still pending.
- Next: OpenClaw Live Create Event Validation

### 2026-04-15 - OpenClaw Exec Tool Strategy

- Goal: Re-anchor the live integration plan on the OpenClaw surface that is actually confirmed to work in Telegram conversations.
- Completed: Reviewed the real OpenClaw Telegram session log and confirmed that the assistant already uses `exec` during live conversation, while shell-invoked one-shot inference paths remain unreliable in the current environment. Added `scripts/molly_create_event.py` as an argv-based Molly Core executor designed for OpenClaw `exec` usage, added bridge helpers to build shell-friendly commands, added tests for the new command-builder and script, and documented the updated strategy in `docs/openclaw_exec_tool_strategy_ko.md` and `docs/openclaw_exec_tool_strategy_en.md`.
- Risks: The strategy is now better aligned with observed runtime behavior, but OpenClaw still needs to be explicitly guided to use the Molly execution command in live conversation. End-to-end validation through the Saekomm bot is still pending.
- Next: Saekomm Live Exec Validation

### 2026-04-15 - Saekomm Python Environment Diagnosis

- Goal: Diagnose why the first live Saekomm-to-Molly execution attempt failed even though OpenClaw had found the Molly entrypoint and built a plausible schedule command.
- Completed: Re-read the latest OpenClaw Telegram session log, confirmed that OpenClaw correctly attempted to call `scripts/molly_create_event.py`, and isolated the failure to interpreter selection rather than business logic. Verified that `python-dotenv` is declared in [`pyproject.toml`](/home/sunghwan/projects/Molly/pyproject.toml), present in Molly's `.venv`, and absent from the system `python3` runtime path used by the failing `exec` command. Updated the Korean and English exec-strategy documents to make `.venv`-based execution an explicit live integration rule. Also hardened `openclaw_molly_bridge.py` so the generated exec command now prefers the project's `.venv/bin/python` path instead of inheriting a potentially wrong interpreter, and revalidated the focused bridge/core tests successfully.
- Risks: Saekomm live scheduling will continue to fail until OpenClaw is prompted or configured to call Molly with `./.venv/bin/python` or the absolute `.venv` interpreter path. The conversation logic is close, but the runtime instruction still needs one more live correction.
- Next: Saekomm Live Exec Validation With `.venv` Interpreter

### 2026-04-15 - Reminder Worker Split

- Goal: Restore reminders and summary delivery in the new OpenClaw-centered runtime where `bot.py` is no longer the always-on process.
- Completed: Identified that reminder logic still existed in `scheduler.py` but was only started from `bot.py`, which meant reminders silently dropped out of the live path after moving conversation to Saekomm/OpenClaw. Added `scripts/run_reminder_worker.py` as a standalone scheduler runtime that validates config, initializes state storage, connects to the configured calendar backend, creates a Telegram bot instance, starts the existing APScheduler jobs, and stays alive independently from the legacy polling bot. Added Korean and English documentation in `docs/reminder_worker_split_ko.md` and `docs/reminder_worker_split_en.md`.
- Risks: The reminder worker still needs to be run as its own long-lived process in production. If neither `bot.py` nor the new worker is running, reminders and summaries will still not be delivered.
- Next: Reminder Worker Startup Validation

### 2026-04-16 - Google To Local Import Path

- Goal: Add a safe, repeatable way to pull existing family schedule data from Google Calendar into Molly's local calendar database now that the Google account has been recovered.
- Completed: Added `calendar_import.py` plus `scripts/import_google_calendar_to_local.py` as the first Google-to-local migration path. Extended the local event schema with optional `source_backend` and `source_event_id` fields plus a uniqueness index so imported Google events can be skipped on re-run instead of duplicated. Implemented conservative normalization for timed and all-day Google events, added guarded support for simple weekly recurrence only, added focused import tests, updated `pyproject.toml`, and documented the migration path in `docs/google_to_local_import_ko.md` and `docs/google_to_local_import_en.md`.
- Risks: Complex Google recurrence patterns are intentionally skipped for now, and the first live run should still be done as a dry-run before writing to local storage. The importer is designed for migration safety, not full bidirectional sync.
- Next: Google To Local Dry-Run Validation

### 2026-04-16 - Google To Local Import Execution

- Goal: Execute the first live migration from Google Calendar into Molly's local calendar DB after verifying the import path with a dry-run.
- Completed: Ran the dry-run import successfully, fixed one Google Calendar API query constraint (`singleEvents=false` cannot be combined with `orderBy=startTime`), then executed the real import. Imported 20 Google events into the local calendar DB with zero duplicates, zero unsupported rows, and zero cancelled rows skipped on this first run. Performed spot checks against local search results to confirm imported family events such as `Beavers` and `Tennis` are now visible through the local calendar repository.
- Risks: Spot checks also showed that local search results may now surface pre-existing local events alongside imported ones, so duplicate-looking user-facing results should be reviewed as part of a later cleanup pass if needed. The importer remains one-way and conservative by design.
- Next: Local Calendar Post-Import Review And Reminder Runtime Setup

### 2026-04-16 - Reminder Worker Runtime Setup

- Goal: Turn the standalone reminder worker into a practical always-on runtime for the new OpenClaw-centered Molly architecture.
- Completed: Added a user-service unit file at `deploy/systemd/molly-reminder-worker.service` for `systemd --user` operation and documented the recommended runtime flow in `docs/reminder_worker_runtime_ko.md` and `docs/reminder_worker_runtime_en.md`, including install, status, restart, stop, and log commands plus a `tmux` fallback.
- Risks: The service file still needs to be installed into the user's systemd directory and started there. If that runtime step is skipped, reminders remain available in code but not active in operation.
- Next: Live User-Service Installation And Validation

### 2026-04-16 - Reminder Worker Live Service Activation

- Goal: Install and activate the standalone reminder worker as a real user-level background service so reminders are live in the local-first Molly runtime.
- Completed: Installed `molly-reminder-worker.service` into `/home/sunghwan/.config/systemd/user/`, reloaded the user systemd daemon, enabled and started the service, and verified that it is running via `systemctl --user status` and `journalctl --user`. Live logs confirmed successful local calendar backend authentication, Telegram bot initialization, scheduler registration, and worker startup.
- Risks: The worker is now running, but reminder behavior still depends on the correctness of the local event data and current per-user reminder calendar subscriptions. User-facing reminder content and cadence may still need tuning during real use.
- Next: Live Reminder Behavior Observation

### 2026-04-16 - OpenClaw Telegram Entry Switch To Molly

- Goal: Replace the Saekomm Telegram entrypoint with the Molly Telegram bot so user conversation and Molly reminder delivery can share the same public bot identity.
- Completed: Confirmed that the Molly project `.env` was already using the Molly bot token, located the OpenClaw Telegram channel setting in `/home/sunghwan/.openclaw/openclaw.json`, and backed up the previous Saekomm-side OpenClaw state into `backups/openclaw_telegram_switch_2026-04-16/` including `openclaw.json`, `SOUL.md`, and `telegram-pairing.json`. Updated the OpenClaw Telegram `botToken` to the Molly bot token, restarted `openclaw-gateway.service`, and verified from gateway logs that the Telegram provider switched over to `@Molly4Kim_bot`.
- Risks: End-to-end conversational validation on the Molly bot is still needed after the token switch. Saekomm backup files are preserved locally, but any future rollback should restore both the OpenClaw config and the desired runtime state together.
- Next: Molly Bot Conversation Validation Through OpenClaw
