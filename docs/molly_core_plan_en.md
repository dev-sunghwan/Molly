# Molly Core Plan

## 1. Goal

This document defines the next Molly Core roadmap.

The priority is no longer just making input easier.
The priority is to make Molly Core a safer and more realistic family scheduling engine:

- accept inputs as candidates when needed
- validate and execute safely
- track where events came from
- handle recurrence, multi-day spans, timezones, and reminders properly

## 2. Design Principles

These principles remain in force:

- final calendar execution stays deterministic Python
- OpenClaw/LLM is limited to interpretation, summarization, extraction, and clarification wording
- Molly Core owns validation, normalization, duplicate suppression, execution, state tracking, and audit behavior
- ambiguous inputs should become candidates or clarification states rather than immediate writes
- event changes should remain traceable later

## 3. Core Workstreams

### 3.1 Candidate Intake

Inputs should be able to enter Molly as candidates rather than forced immediate execution.

The two most important intake paths are:

- Telegram natural language
- Gmail allowlisted email

Recommended flow:

`input -> candidate -> validation -> confirmation/clarification -> execution`

### 3.2 Execution Safety

Molly Core remains responsible for:

- calendar-key validation
- date/time normalization
- recurrence normalization
- duplicate suppression
- destructive-action safety
- source metadata recording

### 3.3 Traceability

Molly should increasingly be able to answer where an event came from.

Examples:

- created directly from Telegram
- created from a Gmail candidate
- imported from Google
- later modified manually
- part of a recurring series

## 4. Priority Roadmap

## Phase A. Gmail Candidate Confirmation

Goal:

- analyze only allowlisted email senders
- confirm in Telegram before execution

Implementation:

- candidate state storage
- Telegram confirmation message format
- `add / ignore / clarification` flow
- Molly Core execution only after confirmation

## Phase B. Source Metadata And Execution History

Goal:

- make event origin and change history easier to inspect

Implementation:

- source type storage
- external message id / thread id storage
- created_by / confirmed_by / updated_by
- execution log cleanup

## Phase C. Edit/Delete Stabilization

Goal:

- make real-world edit/delete flows less risky

Implementation:

- multi-match title handling
- recurring-series partial vs whole edit/delete
- multi-day event editing rules
- clarification on ambiguous deletes

## Phase D. Timezone-Aware Events

Goal:

- reduce timezone confusion during travel or international schedules

Core principle:

- store the event's original local timezone when possible
- allow users to view events in their current viewing timezone
- compute reminders in event timezone while optionally presenting user-facing times in the viewer's timezone

Implementation:

- event-level `timezone` field
- timezone-aware create/update paths
- legacy events default to the system timezone
- display behavior that can surface timezone differences
- reminder calculations using timezone-aware datetimes

Examples:

- London appointment -> `Europe/London`
- Korea travel event -> `Asia/Seoul`

## Phase E. Recurrence Refinement

Goal:

- handle the real-world issues that appear after basic weekly recurrence exists

Implementation:

- delete whole series
- edit/delete a single occurrence
- one-off vs recurring conflict handling
- stronger recurrence duplicate suppression

## Phase F. Reminder Policy Refinement

Goal:

- make reminders more useful at the family-operations level

Implementation:

- separate all-day / timed / multi-day reminder rules
- timezone-aware reminders
- cross-notify rules between family members
- stronger duplicate reminder suppression

## 5. Spouse Input Notification Policy

New requirement:

- if JeeYoung adds a schedule, SungHwan should be notified
- if SungHwan adds a schedule, JeeYoung should be notified

This is different from simple calendar subscription.

The real intent is not "show me the other person's calendar by default."
The real intent is "tell me when my spouse adds or changes a schedule through Molly."

So this should be implemented as a separate event-notification flow, not as reminder subscription sharing.

Recommended policy:

- when Molly executes a real create/update/delete action, record the actor
- if the actor is `SungHwan`, notify `JeeYoung`
- if the actor is `JeeYoung`, notify `SungHwan`
- keep this notification separate from reminders and summaries

Example:

- `SungHwan added [YounHa] Alpha-Math on Fri 17-04 17:00–18:00.`
- `JeeYoung added [Family] Costco on Sat 18-04 All day.`

Longer-term refinements may include:

- separate create/update/delete notification types
- per-event-type spouse notify controls
- always notify both parents for child-related schedules
- fully separate summary/reminder subscriptions from spouse input notifications

## 6. Recommended Order

Most practical order:

1. design spouse input notifications and actor/source metadata
2. Gmail candidate confirmation flow
3. source metadata / execution history
4. edit/delete stabilization
5. timezone-aware event support
6. recurrence refinement
7. reminder policy refinement

## 7. Conclusion

The next Molly Core phase is less about interpretation and more about operational stability.

The roadmap is:

- candidate first
- deterministic execution
- source traceability
- timezone and reminder realism
