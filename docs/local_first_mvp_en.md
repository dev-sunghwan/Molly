# Local-First Molly MVP

## 1. Product Definition

Molly is a local-first family assistant focused on schedule management.

What matters is not rebuilding an external calendar platform, but delivering this experience:

- family members talk to Molly through Telegram or another messenger in natural language
- Molly understands the request and asks follow-up questions when needed
- Molly safely stores and retrieves schedules per family member
- outside schedule information can be handed to Molly easily and turned into schedule candidates
- Molly provides reminders and daily summaries

## 2. Source of Truth

For the MVP, the scheduling system of record is the local SQLite calendar store.

- the local backend is the default store
- Telegram is the main interface
- OpenClaw/LLM acts only as the interpreter
- Google Calendar/Gmail remain optional adapters even if they are restored later

## 3. What the MVP Must Do

### 3.1 Telegram schedule management

- natural-language schedule views
- natural-language event creation
- event updates
- event deletion
- family-member calendar selection
- clarification when the request is ambiguous

### 3.2 Local storage and execution

- preserve one calendar concept per family member
- store events in the local database
- keep deterministic Python validation
- keep audit/logging
- keep reminders and daily summaries

### 3.3 External information intake

Initially, prefer this path over automatic email integration:

- forward or copy-paste email text into Telegram
- paste school / academy / club notice text into Telegram
- later extend to images and PDFs

So the early intake MVP is:

`external notice text -> Telegram -> Molly interpretation -> schedule candidate -> confirmation -> save`

## 4. What the MVP Will Not Try to Do

- rebuild a general calendar platform
- build a complex sharing/permissions model
- implement full invitation/calendar standards
- handle every advanced recurring-event exception
- start from Gmail-dependent automation
- integrate many online services at once

## 5. Input Channel Priority

### Priority 1

- Telegram natural language

Examples:

- `Add YounHa tennis tomorrow at 5pm`
- `Show Haneul school events next week`

### Priority 2

- forwarding external notice text into Telegram

Examples:

- copy-pasted school or academy email text
- pasted club notice text

### Priority 3

- images / PDFs / screenshots

This is a later phase.

### Priority 4

- automatic email intake
- IMAP / forwarding / webhook / Gmail adapter

This is a convenience feature, not the core.

## 6. Product Principles

- Molly's essence is the family-assistant experience.
- External services are optional adapters, not mandatory foundations.
- LLMs are used for understanding and draft generation only; Python executes.
- Molly must ask follow-up questions when needed.
- Telegram usability remains the top near-term priority.

## 7. Next Three Phases

### Phase A. Local Repository Cleanup

- clean up the shared local/google backend interface
- remove leftover backend-specific assumptions from bot and scheduler

### Phase B. Telegram Assistant UX

- expand Telegram natural-language coverage
- connect a real OpenClaw provider
- improve clarification quality

### Phase C. External Notice Intake

- convert pasted/forwarded notice text in Telegram into schedule candidates
- ask clarification questions for person/date/time when needed
- finalize the candidate review and execution flow

## 8. Success Criteria

The MVP succeeds if:

- the family can actually delegate schedule management to Molly through Telegram
- outside notices can be turned into schedule entries conveniently enough
- Molly continues working regardless of Google account state
