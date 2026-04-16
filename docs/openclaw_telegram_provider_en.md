# OpenClaw Telegram Provider

## Goal

The heuristic Telegram parser was useful as a first step, but limited for real natural-language scheduling. This phase adds an OpenClaw-first extraction path that produces a structured draft, while Molly's deterministic Python logic still validates and executes the final action.

## Current Flow

The Telegram natural-language flow now works like this:

1. A user sends a natural-language Telegram message.
2. Molly first tries the configured OpenClaw extractor.
3. If OpenClaw returns a structured draft, `telegram_nlu.py` converts it into the existing intent model.
4. If required fields are missing, Molly asks a clarification question.
5. Final execution still happens through deterministic Python calendar logic.
6. If OpenClaw fails or returns unusable output, Molly automatically falls back to the existing heuristic NLU path.

## What Was Added

- `openclaw_telegram_provider.py`
  - Calls an OpenAI-compatible HTTP endpoint
  - Parses JSON output
  - Converts the result into `ExtractedTelegramDraft`
- `telegram_extractor_provider.py`
  - Selects the extractor based on configuration
- `bot.py`
  - Registers the extractor at startup and falls back to heuristics when unavailable
- `config.py`
  - Adds extractor backend and OpenClaw endpoint settings

## Configuration

The following environment variables are used:

- `MOLLY_TELEGRAM_EXTRACTOR_BACKEND`
  - `heuristic` or `openclaw`
- `OPENCLAW_API_URL`
  - OpenAI-compatible chat completion endpoint URL
- `OPENCLAW_MODEL`
  - Model name to use
- `OPENCLAW_API_KEY`
  - Optional, only when required by the endpoint
- `OPENCLAW_TIMEOUT_SECONDS`
  - Defaults to `20`

## Design Principles

- OpenClaw is used for interpretation assistance only.
- Final calendar creation, update, and deletion remain in deterministic Python logic.
- Even if OpenClaw is wrong or ambiguous, Molly still relies on clarification and deterministic validation before execution.

## Remaining Work

- The actual local OpenClaw endpoint URL and model still need to be filled in through `.env`.
- The email extraction path does not yet have the same level of live provider integration.

## Next Step

The most practical next step is to connect the real local OpenClaw endpoint, then test a handful of real Telegram scheduling phrases and tune the extraction prompt and schema based on those results.
