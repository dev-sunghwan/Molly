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

### 2026-04-16 - Scheduling Fast Path Foundation

- Goal: Reduce OpenClaw scheduling latency by giving it a narrower, more explicit deterministic execution surface for common schedule actions.
- Completed: Added `scripts/molly_schedule_action.py` as a shell-friendly fast-path CLI for `create`, `view`, `search`, `delete`, and `update` actions. Extended `molly_core_requests.py` so Molly Core's structured request boundary now supports view/search/delete/update requests in addition to create-event. Added focused tests for the expanded request parser and the new fast-path script, and documented the design plus an OpenClaw scheduling guidance draft in `docs/openclaw_scheduling_fast_path_ko.md` and `docs/openclaw_scheduling_fast_path_en.md`.
- Risks: OpenClaw is not yet explicitly instructed to prefer this new fast-path CLI in live scheduling conversations, so the execution surface is ready but the runtime prompting layer still needs one tightening pass.
- Next: OpenClaw Scheduling Instruction Tightening

### 2026-04-16 - OpenClaw Scheduling Instruction Draft

- Goal: Write a concrete scheduling-mode instruction draft that can tighten OpenClaw's runtime behavior without destabilizing Molly's broader personality and household-assistant character.
- Completed: Added `docs/openclaw_scheduling_instruction_ko.md` and `docs/openclaw_scheduling_instruction_en.md` with explicit scheduling-mode rules covering scope, clarification behavior, tool priority, response style, and concrete `molly_schedule_action.py` command examples for create/view/search/update/delete. The draft is positioned as an operations rule layer that can be reflected into `SOUL.md` lightly rather than replacing Molly's main personality file.
- Risks: The instruction draft is documented, but not yet directly embedded into OpenClaw's live behavior files. A small SOUL or runtime prompt update is still needed to make the bot consistently follow it.
- Next: Minimal SOUL Scheduling Rule Update And Live Latency Test

### 2026-04-17 - Local Duplicate Event Guard

- Goal: Prevent Molly from inserting duplicate local events repeatedly during Telegram and OpenClaw testing flows.
- Completed: Reviewed the latest OpenClaw Telegram session and confirmed that `Alpha-Math` duplication was appearing both from repeated inserts and from a single-event plus weekly-recurring event being created for the same first occurrence. Updated `local_calendar_backend.add_event()` to check for an existing local event with the same calendar, title, date span, time span, and all-day state before insert, regardless of recurrence payload. When a duplicate slot is detected, Molly now returns an `Already exists` style response instead of inserting another row. Added focused regression tests in `tests/test_local_calendar_backend.py` and verified the local backend test file with `6 passed`.
- Risks: This guard prevents new same-slot duplicates but does not automatically clean up duplicate rows that already exist in the local DB. Near-duplicate events with slightly different titles or times are still allowed by design.
- Next: Clean Existing Duplicate Rows On Request And Consider UI Feedback For Duplicate Suppression

### 2026-04-17 - Existing Duplicate Cleanup

- Goal: Safely clean duplicate local events that had already been inserted during Telegram and OpenClaw testing before the new duplicate guard was added.
- Completed: Added `scripts/cleanup_local_duplicates.py` as a reusable local DB cleanup script with `--dry-run` support. Ran it against the live local calendar DB, kept the weekly recurring `Alpha-Math` series while removing the overlapping one-time duplicate, kept one `Tennis` entry for the `2026-04-16 17:00–18:00` slot while removing four duplicate test rows, and verified afterward that there are no remaining exact same-slot duplicate groups in `local_events`.
- Risks: The cleanup script intentionally only targets same-calendar, same-title, same-date-span, same-time-span duplicates. Similar-but-not-identical events are not touched automatically.
- Next: Observe real usage and only widen duplicate cleanup rules if users start seeing other duplicate patterns in practice

### 2026-04-17 - OpenClaw Bootstrap Context Slim-Down

- Goal: Reduce `/new` session startup latency by shrinking the large OpenClaw workspace context that gets loaded before Molly's first reply.
- Completed: Rewrote `/home/sunghwan/.openclaw/workspace/AGENTS.md` and `/home/sunghwan/.openclaw/workspace/MEMORY.md` to keep only core Molly scheduling rules, household preferences, and privacy guidance. Removed long generic sections about heartbeats, group chat philosophy, broad tool usage, and other non-essential narrative instructions. This reduced `AGENTS.md` from about `11.5 KB` to `2.3 KB` and `MEMORY.md` from about `6.0 KB` to `1.7 KB`.
- Risks: If some previously removed generic OpenClaw behavior turns out to matter in live use, a few short rules may need to be added back selectively. `SOUL.md` is still the largest remaining prompt file in the workspace context.
- Next: Observe `/new` responsiveness in Telegram and only trim `SOUL.md` further if startup still feels too slow

### 2026-04-17 - Recurring Timed Event Expansion Fix

- Goal: Fix incorrect upcoming-view output where weekly timed events were being expanded multiple times but still displayed with their original first occurrence date.
- Completed: Reproduced the issue from the latest OpenClaw Telegram session where `HaNeul swimming` appeared ten times under `Fri 10-04` in an `upcoming` view. Identified the root cause in `local_calendar_backend._row_to_event()`: recurring timed events were using the original stored `start_date` / `end_date` instead of the computed `occurrence_date` when building `dateTime` values. Updated the local backend to use the recurrence occurrence date, added a regression test for recurring timed events, verified `7 passed` in `tests/test_local_calendar_backend.py`, and confirmed that `scripts/molly_schedule_action.py view --scope upcoming` now shows future occurrences on the correct dates.
- Risks: The local recurring engine is still intentionally simple and currently supports only the weekly patterns Molly actively uses. More complex recurrence rules may still need targeted work later.
- Next: Continue real-use observation and fix additional recurrence edge cases only if they appear in practice

### 2026-04-17 - Calendar Label Display In Results

- Goal: Make schedule results easier to scan by showing the target family calendar explicitly on each event line.
- Completed: Updated Molly's result formatting so daily, weekly, monthly, next, upcoming, and search output can show per-event calendar labels in bracket form instead of relying only on grouped headings. Added Korean-friendly labels such as `[윤하]`, `[하늘]`, and `[가족]`, updated the daily formatter to show labels on each line, added focused utils tests, and verified both tests and a live `view --scope today` result.
- Risks: Success messages for create/update/delete still use the existing `Added to YounHa` style and were intentionally left unchanged in this step.
- Next: Observe whether the same Korean label style should also be applied to success and reminder messages

### 2026-04-17 - Dual-Agent And Gmail Intake Planning

- Goal: Evaluate a practical next-step architecture that separates Molly's real household Telegram assistant from a development-focused bot, while reintroducing Gmail only in a tightly scoped and safe way.
- Completed: Added `docs/dual_agent_architecture_ko.md` and `docs/dual_agent_architecture_en.md` to define a two-agent operating model: a lightweight Telegram Fast Agent for real family scheduling and a stronger Slack Dev Agent for development, logs, and operations support. Added `docs/gmail_intake_allowlist_ko.md` and `docs/gmail_intake_allowlist_en.md` to redefine Gmail integration around sender allowlisting, candidate extraction, Telegram confirmation, and deterministic Molly Core execution. Captured the initial wife-address allowlist decision using `jylim3287@gmail.com` as the starting spouse sender.
- Risks: This step is design-only. The Telegram and Slack agents are not yet split in live runtime, and Gmail intake still needs concrete config, workflow state wiring, and confirmation UX implementation before it can be trusted in daily use.
- Next: Implement Telegram-vs-Slack agent separation first, then add Gmail allowlist intake on top of that narrower runtime structure

### 2026-04-17 - Telegram Model Split Groundwork And Gmail Sender Allowlist

- Goal: Convert the dual-agent and Gmail-intake design into concrete Molly-side configuration boundaries and a safe first Gmail filter implementation.
- Completed: Added separate Molly config settings for `OPENCLAW_TELEGRAM_MODEL` and `OPENCLAW_DEV_MODEL`, while keeping the current live runtime on the same model until a lighter Telegram model is chosen in OpenClaw itself. Updated the OpenClaw Telegram extractor to use the Telegram-specific model setting. Added Gmail sender normalization via `gmail_adapter.extract_sender_email()`, introduced `GMAIL_ALLOWED_SENDERS` config loading from `.env`, and enforced sender allowlisting at the start of `assistant_workflow.build_candidate_from_email()`. This means Gmail candidate analysis now ignores non-allowlisted senders before deeper schedule extraction. Updated `.env` with an initial allowlist of `ray.sunghwan@gmail.com` and `jylim3287@gmail.com`. Added regression tests for sender allowlist behavior, inbox recording, and sender normalization, and verified `17 passed` across the focused Gmail/OpenClaw test files.
- Risks: The live OpenClaw runtime is not yet split into distinct Telegram and Slack channels, so this step prepares the Molly-side boundary but does not yet create a second live agent. Gmail still stops at candidate generation and state recording; Telegram confirmation and execution flow still need implementation before inbox processing becomes a daily workflow.
- Next: Configure a real lightweight Telegram agent path in OpenClaw, then implement Gmail candidate confirmation through Telegram before enabling regular inbox processing

### 2026-04-17 - OpenClaw Live Dual-Agent Scaffold

- Goal: Prepare the live OpenClaw runtime so Molly can keep Telegram on a fast household agent while reserving a separate future agent for Slack-based development work.
- Completed: Backed up the current live OpenClaw config to `backups/openclaw_dual_agent_2026-04-17/openclaw.json.bak`. Added an explicit `agents.list` to `/home/sunghwan/.openclaw/openclaw.json` with `main` as the Telegram-facing Molly agent and `molly-dev` as a second isolated agent using a copied workspace at `/home/sunghwan/.openclaw/workspace-dev`. Set the `main` agent defaults toward faster interaction (`thinkingDefault: minimal`, `reasoningDefault: off`, `fastModeDefault: true`) and set the `molly-dev` agent toward deeper development discussion (`thinkingDefault: low`, `reasoningDefault: on`, `fastModeDefault: false`). Added explicit `bindings` so Telegram routes to `main` and future Slack traffic routes to `molly-dev`. Confirmed the new dev workspace exists and observed gateway log lines showing the `agents.list` hot reload was applied successfully.
- Risks: Both agents still use the same model for now, because a validated lighter Telegram model has not yet been selected in the live OpenClaw provider stack. Slack is not yet enabled because app tokens and channel configuration are still missing. Telegram routing was prepared safely, but no fresh post-change conversational validation has been run yet.
- Next: Validate Telegram still behaves normally on the `main` agent, then add Slack app credentials and enable the Slack channel so `molly-dev` can become the development bot

### 2026-04-17 - Plain Text Schedule Formatting For OpenClaw Replies

- Goal: Stop raw HTML tags such as `<b>...</b>` from leaking into Molly Telegram replies now that OpenClaw is relaying Molly Core output as plain text rather than as Telegram HTML.
- Completed: Removed HTML formatting from Molly's schedule output builders in `utils.py` and `calendar_repository.py`, so daily, weekly, monthly, search, next, and upcoming responses now render as plain text without embedded markup. Verified the daily CLI output now returns `📅 Friday, 17-04` style text instead of `📅 <b>Friday, 17-04</b>`, and re-ran the focused formatting/backend test set with `21 passed`.
- Risks: The legacy Python Telegram bot still uses `parse_mode="HTML"` in several reply paths, but plain text output remains valid there as well. If rich formatting is ever desired again, it should be applied at the outer Telegram delivery layer rather than embedded inside Molly Core strings.
- Next: Re-test Molly Telegram replies after the formatting cleanup, then continue latency reduction by shrinking OpenClaw per-turn context rather than changing Molly Core output

### 2026-04-17 - Telegram Fast Workspace Cutover

- Goal: Strip Telegram down to a lightweight scheduling-focused agent instead of a richer household persona, so OpenClaw spends less time loading irrelevant bootstrap context for routine schedule turns.
- Completed: Verified that a lighter alternate model is not currently surfaced in the live OpenClaw setup, so the immediate speed path had to focus on context reduction rather than model swapping. Created a new Telegram-only workspace at `/home/sunghwan/.openclaw/workspace-fast` with very small bootstrap files focused only on Molly scheduling execution. The new bootstrap footprint is roughly `AGENTS 1202`, `SOUL 570`, `MEMORY 168`, `IDENTITY 81`, `TOOLS 82`, `USER 107`, `BOOTSTRAP 62` bytes, far below the previous Telegram workspace prompt footprint. Updated `/home/sunghwan/.openclaw/openclaw.json` so the `main` Telegram agent now uses `workspace-fast`, has `thinkingDefault: off`, `reasoningDefault: off`, `fastModeDefault: true`, and an empty per-agent skills list. Also enabled `agents.defaults.contextInjection: continuation-skip` so completed continuation turns can skip full workspace bootstrap re-injection. Restarted the gateway and confirmed from service logs that the embedded runtime backend now starts with `cwd: /home/sunghwan/.openclaw/workspace-fast`.
- Risks: Telegram and dev agents still share the same model (`openai-codex/gpt-5.4`), so the improvement ceiling is limited until a verified lighter model is added to the OpenClaw model stack. The speed change should still help on context-heavy turns, but it may not be dramatic enough if provider-side model latency dominates.
- Next: Run fresh Telegram turn validation on Molly bot, compare latency against the prior `~8.4s` baseline for `오늘 전체 일정 알려줘`, and only then decide whether a lighter model must be added externally for further gains

### 2026-04-17 - Molly Core Plan And Spouse Cross-Notify Baseline

- Goal: Document the next Molly Core roadmap around candidate-confirmation, execution traceability, timezone-aware scheduling, and reminder realism, while also addressing a concrete household reminder requirement.
- Completed: Added `docs/molly_core_plan_ko.md` and `docs/molly_core_plan_en.md` to define the Molly Core roadmap, including Gmail candidate confirmation, source metadata, edit/delete stabilization, event-level timezone support for travel scenarios, recurrence refinement, and reminder policy refinement. After clarifying the spouse-notification requirement, corrected the plan so this feature is treated as a separate actor-based notification flow rather than shared calendar subscriptions. Reverted the temporary `config.json` reminder subscription broadening so daily summaries and reminder subscriptions remain scoped as before.
- Risks: Spouse input notification is not implemented yet. It now has the right design direction, but still needs actor metadata, a notification trigger point after successful Molly execution, and a clean message format.
- Next: Implement spouse input notifications as a separate post-execution notification path, then continue with Gmail candidate confirmation and timezone-aware event design

### 2026-04-17 - Spouse Input Notification Implementation

- Goal: Notify one spouse when the other adds, updates, or deletes a schedule through Molly, without overloading reminder subscriptions or daily summaries.
- Completed: Added `spouse_notifications.py` as a dedicated helper for spouse-to-spouse schedule-change notifications. The notification logic now maps `SungHwan <-> JeeYoung`, formats concise Korean notification messages, and supports create/update/delete/delete-series actions. Extended `MollyCore._record_result()` to persist `actor_user_id` and `actor_name` into execution metadata. Updated both live execution paths so spouse notifications can fire after successful schedule mutations: the legacy Telegram `bot.py` path now sends async spouse notifications after successful Molly execution, and the OpenClaw-facing CLI scripts `scripts/molly_schedule_action.py` and `scripts/molly_create_event.py` now accept `--actor-user-id`, record actor metadata, and trigger spouse notifications synchronously when provided. Also updated the Telegram fast OpenClaw workspace instructions so Molly CLI executions should pass `--actor-user-id` from Telegram sender metadata whenever available. Added focused tests for spouse-target mapping, spouse-notification formatting, actor metadata recording, and CLI help coverage; verified the focused test set passes.
- Risks: For the current OpenClaw live path, spouse notifications depend on the agent actually including `--actor-user-id` in the Molly CLI command. The rule is now present in the fast workspace instructions, but model-mediated execution still needs real-use validation. Notification delivery is currently tied to successful mutating actions only and does not yet distinguish between create/update/delete notification preferences.
- Next: Validate a real Telegram create flow with actor-user-id present, then decide whether spouse notifications should remain enabled for update/delete as well as create

### 2026-04-16 - Timed Multi-Day Event Support

- Goal: Support family events that span multiple days with real start and end times, such as camps, trips, and overnight activities, instead of only supporting all-day multi-day ranges.
- Completed: Extended command parsing to accept timed multi-day input in the form `add <calendar> <title> <start_date> <start_time> to <end_date> <end_time>`, updated the command-to-intent adapter and Molly Core request boundary to carry an optional end date for timed events, updated both local and Google calendar backends to store and execute timed multi-day events correctly, improved event formatting so cross-day timed events display with full span information, and updated week/month grouping to surface spanning events on each covered day. Added focused tests for parser, intent, backend, request, and OpenClaw bridge behavior. Also corrected the existing `Cub Indoor Camp` local record so it now spans from the evening of 2026-04-17 through 2026-04-19 16:00 in local storage.
- Risks: Natural-language extraction for timed multi-day events is still likely to work best when the request is phrased clearly, because the heuristic fallback remains simpler than the deterministic command surface. More advanced rescheduling flows for timed multi-day events may still need future refinement.
- Next: Live Molly Bot Validation For Timed Multi-Day Scheduling

### 2026-04-16 - OpenClaw Speed Tuning Pass 1

- Goal: Reduce Molly Telegram response latency by shrinking OpenClaw's per-turn tool and session overhead without breaking Molly Core execution.
- Completed: Reviewed the live OpenClaw session transcript and confirmed that the main delay was not Molly Core execution but heavy OpenClaw context assembly plus large tool schema overhead. Inspected `/home/sunghwan/.openclaw/openclaw.json`, confirmed the gateway had been running with `tools.profile: "coding"`, and switched it to a much tighter policy: `tools.profile: "minimal"` with `tools.allow: ["group:runtime"]`. This preserves `exec` and `process` for Molly scheduling scripts while removing file, memory, web, session-spawn, and other coding-oriented tool surfaces from normal Telegram turns. Added `session.reset.idleMinutes: 180` so stale long-lived DM sessions can roll over automatically after inactivity. Backed up the previous OpenClaw config to `/home/sunghwan/.openclaw/openclaw.json.bak-2026-04-16-speed-tune`, confirmed the config hot-reloaded, and restarted `openclaw-gateway.service` cleanly.
- Risks: Existing live Telegram conversations may still feel heavy until they start a fresh session, because the old transcript history still exists even after tightening the tool policy. The new minimal policy intentionally removes memory and filesystem tools, so if future non-scheduling assistant behavior needs those again, it may require a more targeted per-agent or per-provider split instead of a single global profile.
- Next: Fresh-Session Molly Bot Latency Validation

### 2026-04-17 - OpenClaw Scheduling Recovery And Weekly Recurrence CLI

- Goal: Recover broken live scheduling execution after the first speed-tuning pass and add weekly recurring-event support to Molly's fast execution surface.
- Completed: Re-reviewed the latest Telegram session logs and confirmed that the primary failure mode was no longer "calendar missing", but OpenClaw failing to actually execute the Molly CLI in some fresh-session scheduling turns. Tightened the live workspace instructions so schedule lookups must execute rather than merely announce intent, and adjusted OpenClaw tool policy again from `minimal + runtime` to a `coding` base with aggressive `deny` rules. This restored real `exec` usage in the live Telegram path: in the latest successful lookup turn, OpenClaw called `molly_schedule_action.py view --scope today`, the Molly CLI returned the real local-calendar result in about 0.8s, and the full user-visible response completed in about 4.8s total. Also traced a later create-event failure to an invalid OpenClaw-invented calendar key (`primary`) rather than a backend problem, after which OpenClaw recovered by reading Molly config and retrying with `YounHa`. On the Molly side, added weekly recurrence support to `scripts/molly_schedule_action.py create` and `scripts/molly_create_event.py` via `--recurrence` and `--weekly-day` options, added request-boundary and script tests, and updated live AGENTS instructions with a weekly recurring event example.
- Risks: OpenClaw still occasionally reasons about Molly's calendar surface instead of going straight to execution, so live behavior is improved but not yet fully deterministic. Recurrent-event support is now exposed in the Molly CLI layer, but OpenClaw still needs to learn to use it consistently from natural-language Telegram turns. Calendar-key hallucinations like `primary` are still possible until live prompting is tightened further or aliases are added deliberately.
- Next: Live Telegram Validation For Weekly Recurring Event Creation

### 2026-04-17 - Live Prompt Tightening For Recurrence And Calendar Mapping

- Goal: Reduce remaining scheduling ambiguity in fresh Telegram sessions by teaching OpenClaw the exact Molly calendar keys and how to translate simple recurring language into Molly's weekly recurrence flags.
- Completed: Updated the live OpenClaw workspace instructions in `AGENTS.md` so the agent now has an explicit family-member-to-calendar-key map (`sunghwan`, `jeeyoung`, `younha`, `haneul`, `younho`, `family`), a direct prohibition against inventing keys like `primary`, and concrete recurrence phrase mappings such as `매주 금요일 -> --weekly-day FR`. Also tightened `SOUL.md` so create/update requests with plausible date ambiguity should trigger clarification instead of date guessing.
- Risks: These changes strengthen the runtime prompt, but the behavior is still model-mediated. OpenClaw may still occasionally need another nudge if it prioritizes conversation over execution in a particular turn.
- Next: Live Telegram Validation For Weekly Recurring Event Creation And Date Clarification

### 2026-04-17 - Gmail Candidate Confirmation Flow Baseline

- Goal: Turn Molly's Gmail ingestion from one-way candidate detection into a real workflow with stored candidates, Telegram notification text, and deterministic confirm/ignore actions.
- Completed: Extended `state_store.py` with a new `email_candidates` table and helper methods for saving, listing, notifying, and updating Gmail candidate decisions. Updated `inbox_processor.py` so every newly processed Gmail message now stores a structured candidate record and links its `processed_inputs` row back to a `candidate_id`. Added `gmail_confirmation.py` as the Molly Core boundary for candidate confirmation: it formats Telegram-facing candidate messages, lists pending candidates, confirms a candidate by reconstructing its stored intent and executing it through `MollyCore`, and supports explicit ignore actions. Added a new CLI entrypoint at `scripts/molly_gmail_action.py` with `process`, `list`, `confirm`, `ignore`, and `notify-pending` subcommands so Gmail intake can now be operated deterministically without touching the legacy Telegram bot. Added focused tests for candidate storage, inbox persistence, Gmail confirmation behavior, and the new script surface.
- Risks: The live OpenClaw/Telegram path does not yet automatically route user replies like `gmail confirm 12` into this new Gmail action CLI, so the current implementation is a Molly Core-complete baseline rather than a full live UX. Notification messages are also sent to all allowed Telegram users for now; later, this may need a narrower policy if Gmail candidate visibility should be limited.
- Next: Wire OpenClaw or a lightweight inbox worker to call `scripts/molly_gmail_action.py process --notify`, then add a live confirmation route so Telegram replies can trigger `confirm` and `ignore` directly

### 2026-04-18 - Gmail Live Fast-CLI Integration

- Goal: Make Gmail candidate commands usable from the live Telegram/OpenClaw runtime instead of leaving them as a separate Molly-only CLI surface.
- Completed: Extended `scripts/molly_schedule_action.py`, which is the main OpenClaw fast-path CLI, with four Gmail subcommands: `gmail-process`, `gmail-list`, `gmail-confirm`, and `gmail-ignore`. These now expose the Gmail candidate workflow through the same JSON-returning execution path already used for calendar lookups and schedule changes. Updated the fast OpenClaw workspace instructions in `/home/sunghwan/.openclaw/workspace-fast/AGENTS.md` so the Telegram agent is told to use these subcommands directly for inbox review and explicit `gmail confirm <id>` / `gmail ignore <id>` commands, while still passing `--actor-user-id` when available. Added CLI coverage tests for the new help surface and re-ran the focused Gmail/state/inbox/script test set successfully.
- Risks: This is still prompt-mediated live behavior. The Telegram agent now has the right CLI surface and instructions, but real-world confirmation still depends on OpenClaw following them consistently. Gmail candidate review also remains intentionally simple: the current stored candidate summary may still miss richer fields like location or notes from forwarded mail.
- Next: Validate a real Telegram turn using `gmail list` or `gmail confirm <id>`, then improve candidate extraction quality for forwarded family activity emails

### 2026-04-18 - Gmail Allowlist Expansion For Hanwha Address

- Goal: Allow Molly to treat `sunghwan.k@hanwha.com` as a trusted Gmail sender alongside the existing personal and spouse addresses.
- Completed: Added `sunghwan.k@hanwha.com` to `GMAIL_ALLOWED_SENDERS` in `.env`. This means future inbox scans will no longer reject forwarded scheduling mail from that address solely because of the sender check.
- Risks: Existing messages that were already stored as `ignored` because of the old allowlist do not automatically reclassify. They need to be reprocessed explicitly, and they may still need better extraction if the body contains forwarded-mail noise.
- Next: Reprocess the previously ignored AWS Summit mail and verify whether it now becomes a real candidate or whether extraction quality also needs improvement

### 2026-04-18 - Forwarded Email Extraction Fixes And Gmail Command Tightening

- Goal: Fix two live Gmail issues at once: poor candidate extraction from forwarded emails like AWS Summit and Cubs notices, and weak live routing for exact Telegram commands like `gmail list`.
- Completed: Strengthened the Telegram fast OpenClaw instructions in `/home/sunghwan/.openclaw/workspace-fast/AGENTS.md` so `gmail list`, `gmail confirm <id>`, `gmail ignore <id>`, and `gmail process` are now explicitly treated as Molly CLI commands rather than generic Gmail questions, with an explicit prohibition against falling back to memory search, docs lookup, or abstract Gmail help flows. On the Molly side, improved forwarded-email extraction in `assistant_workflow.py` and `utils.py`: added month-name date parsing, AM/PM and dotted-time parsing, whole-line time-range extraction, line-level body cleanup to drop forwarded header noise, and body-first calendar scoring so child names like `YounHa` win over sender/header noise. Added focused regression tests for forwarded AWS Summit and Cubs emails and re-ran the Gmail/state/inbox/script test set successfully. Requeued and reprocessed the AWS and Cubs messages in the live inbox, and both now resolve as `READY`/`pending_confirmation`.
- Risks: The OpenClaw side is still prompt-mediated, so a real Telegram turn should still be tested to confirm that `gmail list` now routes directly to `molly_schedule_action.py gmail-list`. Forwarded emails with very noisy HTML-only bodies or attachment-only calendar data may still need a richer extraction layer later.
- Next: Live Telegram validation for `gmail list` and `gmail confirm <id>`, then optional enrichment of candidate summaries with location/notes for family activity mails
