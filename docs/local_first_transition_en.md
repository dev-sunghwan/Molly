# Molly Local-First Transition Record

## 1. Background

Molly was originally designed around a dedicated Gmail account and Google Calendars managed under that account as the scheduling system of record.

That approach was practical for getting started quickly, but on 2026-04-15 the Molly Google account was disabled under suspected policy abuse. That made the operational risk of a Google-centered architecture explicit.

This incident showed three things clearly:

- Molly's core value is the family scheduling assistant itself, not the Google account.
- If external account policy and platform review status control overall system availability, the long-term operational risk is too high.
- Core assets such as Telegram, deterministic Python logic, clarification flow, and SQLite state storage remain valuable even without Google.

This record explains why Molly began seriously considering a transition from a Google-centered architecture to a local-first one.

## 2. Transition Goal

The new goal is:

- move Molly's source of truth into local storage
- keep Telegram as the main interface
- keep OpenClaw/LLM use limited to interpretation
- reduce Google Calendar and Gmail from mandatory backends to optional adapters
- allow Molly development and day-to-day use to continue regardless of Google account recovery

In one line:

`Telegram -> OpenClaw/LLM -> Molly Core -> Local Calendar Store`

## 3. What Stays and What Changes

Keep:

- Telegram bot interface
- intent schema
- clarification flow
- SQLite state storage
- deterministic Python validation / execution policy
- scheduler / reminder structure
- OpenClaw integration direction

Replace or demote:

- Google Calendar as the default execution backend
- Gmail as the default ingestion channel
- Google OAuth / token-centered operation

This is closer to a backend migration than a full rewrite.

## 4. Recommended Target Structure

### 4.1 Core

- `ScheduleIntent`
- validation / normalization
- clarification
- execution policy

### 4.2 Local Calendar Store

- SQLite-backed calendars / events / reminders
- keep one calendar concept per family member
- preserve audit and replay protection

### 4.3 Interfaces

- Telegram: primary input and response channel
- Email: future adapter
- Optional sync adapters: Google, ICS, CalDAV, and others

### 4.4 Adapters

- OpenClaw adapter: natural-language interpretation
- Google adapter: optional future sync or import/export if recovery succeeds
- Email adapter: provider-agnostic direction rather than Gmail-only

## 5. Why Local-First Fits Better

### 5.1 Advantages

- Less dependent on external account suspension risk
- Source of truth stays inside the project boundary
- Testing and local development become simpler
- Safety rules and audit logs can be designed directly
- Long-term vendor lock-in is reduced

### 5.2 Costs

- There is no ready-made external calendar UI by default
- External invites and sharing workflows need more custom design
- Email ingestion will need an alternative provider strategy

## 6. Draft Migration Plan

### Step 1. Back Up Existing Google Data

- Back up as much Molly Gmail data as possible
- Export existing Google Calendar events
- Record the existing calendar structure and calendar ids

### Step 2. Introduce a Local Calendar Schema

- `calendars`
- `events`
- `event_recurrence`
- `reminders`
- `event_log`

### Step 3. Separate the Execution Backend

- Separate current Google Calendar writes from the Molly core execution boundary
- Introduce a local SQLite backend as the new default execution target

### Step 4. Prioritize Real Telegram Usage

- Telegram natural language -> local backend create/update/delete
- Move views / reminders / daily summary to the local backend

### Step 5. Add Import / Sync Layers

- Google export import
- optional Google sync
- optional ICS export

### Step 6. Redesign Email

- Revisit email ingestion as provider-agnostic instead of Gmail-only
- Consider IMAP, forwarding, or webhook-based intake if needed

## 7. Operating Principles

- Molly core must remain independently usable regardless of Google recovery.
- Even if Google is reattached later, it should remain an optional adapter.
- Deterministic Python execution and auditability remain required.
- Telegram usability remains the near-term product priority.

## 8. Next Design Work

The next items to make concrete are:

- a first local calendar schema draft
- a shared repository interface for Google and local backends
- an event import plan
- reprioritization of day-to-day Telegram features against the local backend

The concrete MVP scope and input-channel priority are documented separately in [local_first_mvp_en.md](/home/sunghwan/projects/Molly/docs/local_first_mvp_en.md:1).
