# Gmail Intake Allowlist Plan

## 1. Goal

Allow Molly to analyze a limited subset of emails arriving at `molly.kim.agent@gmail.com` and convert relevant ones into schedule candidates.
The initial version should stay intentionally narrow and safe.

## 2. Initial Scope

Only analyze emails from:

- the user's own email address
- `jylim3287@gmail.com`

All other senders should be excluded from automatic scheduling analysis by default.

This reduces:

- noise
- false positives
- accidental event creation
- early-stage Gmail automation complexity

## 3. Recommended Flow

Recommended flow:

`Gmail Inbox -> Sender Allowlist Filter -> Email Extraction -> Schedule Candidate -> Molly Confirmation -> Local Calendar Write`

Initial operating rules:

- do not auto-create by default
- produce a candidate first
- require confirmation
- keep final writes in deterministic Molly Core Python

## 4. Processing Stages

### 4.1 Collection

- fetch recent inbox messages via Gmail API
- extract message id, thread id, subject, sender, date, and body

### 4.2 Filtering

- parse sender email address
- pass only allowlisted senders into deeper analysis
- record other emails as ignored states such as `ignored_not_allowlisted`

### 4.3 Extraction

LLM/OpenClaw is responsible only for:

- summarizing the email
- making a first-pass schedule relevance judgment
- extracting candidate title, date, time, person, and place
- surfacing ambiguity

### 4.4 Validation

Deterministic Python validates:

- target family member
- normalized date and time
- required fields
- duplicate risk
- recurrence handling

### 4.5 Confirmation

Initially, Telegram should be the confirmation channel.

Suggested confirmation payload:

- email subject summary
- extracted schedule candidate
- target calendar
- add / reject prompt

Example:

`I found a schedule candidate from AWS Summit London 2026: [Sunghwan] 2026-04-20 15:00~16:00. Should I add it?`

### 4.6 Execution

- after confirmation, execute via `molly_schedule_action.py create` or equivalent Molly Core path
- store execution result and source metadata

## 5. Why Confirmation-First Is Better

Email is more ambiguous than direct Telegram commands.
Early-stage safety should protect against:

- promotional or administrative emails being misread as schedule items
- selecting the wrong time among several candidates
- choosing the wrong calendar
- creating duplicates

So the initial policy should be:

- allowlisted sender
- candidate only
- Telegram confirmation
- deterministic execution

## 6. State Model

Gmail intake should track workflow state such as:

- `new`
- `ignored_not_allowlisted`
- `ignored_not_schedule_related`
- `candidate_ready`
- `needs_clarification`
- `confirmed`
- `executed`
- `skipped_duplicate`

Message-id-based idempotency should also be preserved.

## 7. Suggested Config

Useful explicit settings:

- `GMAIL_INTAKE_ENABLED=true|false`
- `GMAIL_ALLOWED_SENDERS=ray.sunghwan@gmail.com,jylim3287@gmail.com`
- `GMAIL_CONFIRMATION_MODE=telegram`
- `GMAIL_AUTO_CREATE=false`

Recommended initial defaults:

- enabled only when needed
- auto create off
- Telegram confirmation on

## 8. LLM vs Python Boundary

LLM/OpenClaw:

- email summarization
- first-pass schedule relevance
- structured candidate extraction
- clarification wording

Python:

- sender allowlist checks
- date/time normalization
- calendar mapping validation
- duplicate suppression
- state transitions
- actual create/update execution

## 9. Suggested Delivery Phases

### Phase A. Redefine Gmail Intake Around Allowlist

- add explicit allowed sender list
- ignore non-allowlisted messages early

### Phase B. Candidate Pipeline

- store candidate instead of auto-creating
- define Telegram confirmation message format

### Phase C. Confirmation Flow

- add confirm / reject handling in Telegram
- execute Molly Core only after confirmation

### Phase D. Limited Automation

- after stability, consider auto-create only for well-understood email categories

## 10. Conclusion

Gmail can be reintroduced, but it should be treated as a safe intake channel rather than the system of record.

The initial strategy is:

- sender allowlist
- candidate extraction
- Telegram confirmation
- deterministic calendar execution
