# Dual-Agent Architecture

## 1. Goal

Running Molly as one long-lived agent mixes real household scheduling context with development and debugging context.
This document proposes splitting Molly into two agents:

- Telegram Fast Agent
- Slack Dev Agent

The goals are:

- improve Telegram response speed
- separate household scheduling context from development context
- reduce OpenClaw context overhead
- provide a stronger-model channel for development and operations work

## 2. Recommended Structure

Recommended runtime shape:

`Telegram Molly Bot -> Telegram Fast Agent -> Molly Core -> Local Calendar DB`

`Slack Dev Bot -> Slack Dev Agent -> Molly Core / Logs / Docs / Dev Tools`

Both agents may call Molly Core, but their responsibilities and allowed behavior should remain separate.

## 3. Telegram Fast Agent

### 3.1 Purpose

- real family-facing scheduling assistant
- fast responses and short clarification loops
- create/view/update/delete schedule actions

### 3.2 Model Direction

- lighter model
- lower reasoning cost
- short context

### 3.3 Behavior Rules

- prefer Molly fast scheduling CLI for scheduling requests
- avoid memory and filesystem exploration by default
- execute immediately when the request is complete
- ask only short clarification questions when required
- keep final calendar mutation in deterministic Python

### 3.4 Prompt Context

- short `SOUL.md`
- short `AGENTS.md`
- minimal household memory
- retain only scheduling rules, family-calendar mapping, and recurrence mapping

## 4. Slack Dev Agent

### 4.1 Purpose

- development support
- operations checks
- log analysis
- design discussion
- debugging and reproduction help

### 4.2 Model Direction

- stronger model
- deeper reasoning allowed
- larger context acceptable

### 4.3 Behavior Rules

- optimize for development productivity rather than end-user latency
- longer explanations are acceptable
- may call Molly Core when needed, but its default role is dev/ops assistance
- should not perform destructive calendar changes without explicit intent

## 5. Why This Split Matters

Current Telegram latency is driven more by OpenClaw context and reasoning overhead than by Molly Core execution time.
That makes the following split useful:

- keep the real scheduling path small and fast
- move development and debugging to a separate agent

This also reduces:

- dev conversations polluting the household assistant context
- overly long Telegram replies
- unnecessary tool/schema/context loading

## 6. Suggested Permission Boundary

Telegram Fast Agent:

- allow: Molly scheduling CLI and minimal runtime execution
- restrict: broad file exploration, large document reads, memory search, dev-heavy tools

Slack Dev Agent:

- allow: docs, logs, tests, and Molly CLI when needed
- restrict: destructive production calendar actions without explicit request

## 7. Implementation Strategy

### Phase A. Context Split

- minimize Telegram Fast Agent workspace context
- define a separate workspace or prompt profile for Slack Dev Agent

### Phase B. Model Split

- use a lighter model for the Telegram-connected agent
- use a stronger model for the Slack-connected agent

### Phase C. Channel Split

- Telegram bot becomes the household runtime channel
- Slack bot becomes the development and operations channel

### Phase D. Operational Validation

- validate Telegram create/view latency
- validate Slack dev-agent usefulness for logs, design, and debugging

## 8. Boundary With Molly Core

Both agents can call Molly Core, but these responsibilities remain deterministic Python:

- date/time normalization
- calendar-key validation
- duplicate prevention
- recurrence generation
- create/update/delete/search execution

Agents remain responsible for:

- natural-language interpretation
- clarification wording
- email summarization
- schedule candidate extraction

## 9. Suggested Priority

Recommended order:

1. document Telegram Fast Agent and Slack Dev Agent roles
2. configure a lighter model and smaller context for Telegram
3. add Slack bot and Slack agent
4. re-check Telegram latency
5. add Gmail intake on top of this structure

## 10. Conclusion

Dual-agent is not architecture theater. It fits Molly's current problems well.

- Telegram should stay narrow and fast
- Slack should stay broader and deeper
- Molly Core should remain the deterministic execution layer

This is the most practical incremental path without a rewrite.
