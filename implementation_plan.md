# Molly: Family Calendar Telegram Assistant — Implementation Plan

> **Decisions confirmed by SungHwan (2026-04-08)**
> - Telegram library: `python-telegram-bot` v13 (sync) — migrate to v20 async in Phase 2 if needed
> - Calendar name = person's first name (exact match required)
> - Date format: `DD-MM-YYYY` (British) + `today`, `tomorrow`, day-name shortcuts (`Mon`–`Sun`) — consistent throughout
> - Timezone: `Europe/London` — fixed, revisit only if travel scenarios arise
> - Platform: **Windows** (initially); project root is `<project_root>/` (OS-neutral notation)
> - `today` / `tomorrow` always query **all 6 calendars** — no per-calendar filter in Phase 1
> - Phase 1 write command: **`add` only** — no delete/edit until Phase 2
> - Reminders/scheduler: **Phase 2 only**

## 1. Project Objective

Build a lightweight, always-on Python service that runs on a Windows PC, responds to Telegram messages from SungHwan (and later, family members), and reads/writes events to six dedicated Google Calendars. The bot is the interface; Google Calendar is the system of record. No LLM, no database, no web UI.

---

## 2. MVP Scope (Phase 1)

- Respond to Telegram messages via polling
- Parse a simple, semi-structured command format
- Add an event to a specified calendar via `add` command
- List today's events across **all 6 calendars** (fixed — no per-calendar filter)
- List tomorrow's events across **all 6 calendars** (fixed)
- Authorize with Google Calendar via OAuth 2.0 (local machine flow)
- Run continuously in the background on Windows

---

## 3. Out-of-Scope (Phase 1)

| Item | Phase |
|------|-------|
| Natural language parsing / LLM | Phase 3+ |
| Multi-user Telegram support (JeeYoung, children) | Phase 2 |
| Reminders / notifications | Phase 2 |
| Recurring events | Phase 2 |
| Event editing / deletion | Phase 2 |
| Slack integration | Out of scope |
| Web UI or dashboard | Out of scope |
| Database (SQLite etc.) | Not needed Phase 1 |
| Webhooks for Telegram | Phase 2+ |

---

## 4. Recommended System Architecture

```
[SungHwan's iPhone / Telegram App]
        |
        | Telegram Cloud (polling)
        |
[Windows PC — always running]
  ┌─────────────────────────────────┐
  │  molly/                         │
  │  ├── bot.py          (main loop)│
  │  ├── commands.py     (parsing)  │
  │  ├── calendar_client.py (GCal)  │
  │  ├── config.py       (settings) │
  │  └── utils.py        (helpers)  │
  └─────────────────────────────────┘
        |
        | Google Calendar API (HTTPS)
        |
[Google Calendar — 6 family calendars]
```

**Key design principle:** No abstract layers. Each file has one clear job. The main loop is in bot.py and calls everything else directly.

---

## 5. Main Runtime Flow

```
1. bot.py starts
2. Load config (config.json or .env)
3. Authenticate with Google Calendar (load token.json if exists; else run OAuth browser flow)
4. Start Telegram polling loop
5. For each incoming message:
   a. Check sender is authorized (Telegram user ID whitelist)
   b. Parse the message text → identify command
   c. If "today" → fetch today's events from GCal → format → reply
   d. If "tomorrow" → fetch tomorrow's events → format → reply
   e. If "add ..." → parse calendar/title/date/time → insert GCal event → confirm reply
   f. If unrecognized → send help/usage reply
6. Loop continues indefinitely (errors logged, not crashing the loop)
```

---

## 6. Recommended Python Modules / Files

| File | Responsibility |
|------|---------------|
| `bot.py` | Telegram polling loop, message dispatch, entry point |
| `commands.py` | Parse raw text into structured command objects |
| `calendar_client.py` | All Google Calendar API calls (auth, list, insert) |
| `config.py` | Load and expose config values (bot token, calendar IDs, timezone, whitelist) |
| `utils.py` | Date/time parsing helpers, text formatting for replies |
| `run.bat` | Windows batch script to start the bot (activates venv, launches bot.py) |

> **No classes required for MVP.** Simple functions are fine. Introduce a class only if `calendar_client.py` becomes complex.

---

## 7. Data / Config That Must Be Stored Locally

| File | Contents | Sensitive? |
|------|----------|------------|
| `config.json` | Calendar IDs, timezone, authorized Telegram user IDs | No |
| `.env` | Telegram Bot Token | **Yes** |
| `credentials.json` | Google OAuth 2.0 client credentials (downloaded from GCP Console) | **Yes** |
| `token.json` | Google OAuth refresh token (auto-generated on first run) | **Yes** |

**Assumptions:**
- `.env` and `credentials.json` and `token.json` are listed in `.gitignore`
- `config.json` contains no secrets (only IDs and preferences)

---

## 8. External Services and Credentials Needed

### Telegram
- Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
- Obtain the **Bot Token** → store in `.env` as `TELEGRAM_BOT_TOKEN`
- Find SungHwan's Telegram **User ID** (use @userinfobot or log it from first message)
- Store allowed user IDs in `config.json`

### Google Calendar (GCP)
- Log into [Google Cloud Console](https://console.cloud.google.com) with the dedicated Gmail account
- Create a new GCP project (e.g., `molly-family-cal`)
- Enable the **Google Calendar API**
- Create **OAuth 2.0 credentials** (type: Desktop app)
- Download `credentials.json`
- On first run, the app opens a browser for OAuth consent → generates `token.json`

### Calendar IDs
- In Google Calendar UI, go to each calendar's settings → copy **Calendar ID**
- Store all 6 in `config.json` as a dictionary keyed by short name (e.g., `"SungHwan"`, `"JeeYoung"`, etc.)

---

## 9. Google Calendar Integration Strategy

**Library:** `google-api-python-client` + `google-auth-oauthlib`

> **Sync vs Async note:** `python-telegram-bot` v13 uses a synchronous threading model — the polling loop runs in the main thread and each message handler fires in a worker thread. This is simpler to reason about for a solo builder. v20 uses Python `asyncio` and is more efficient under high load, but adds `async/await` complexity everywhere. For a family bot with <10 messages/day, sync is perfectly fine. Migration path to v20 is straightforward: the core logic in `commands.py`, `calendar_client.py`, and `utils.py` is not async-specific and can stay unchanged.

**Auth flow:**
1. Check if `token.json` exists and is valid
2. If not, run `InstalledAppFlow` (opens default browser on Windows) → saves `token.json`
3. All subsequent runs use the refreshed token (refresh is automatic)

**Scopes needed:** `https://www.googleapis.com/auth/calendar`

**Key operations:**
- `events().list(calendarId=..., timeMin=..., timeMax=..., singleEvents=True, orderBy='startTime')` → read events
- `events().insert(calendarId=..., body={...})` → create event

**Calendar name → ID resolution:**
- `config.json` maps friendly names to Google Calendar IDs
- Commands reference friendly names (e.g., `YounHa`) → resolved to ID before API call
- Case-insensitive matching preferred

**Date/time handling:**
- Timezone fixed at `Europe/London` in `config.json` — no multi-timezone support in Phase 1
- All events inserted with explicit timezone
- "tomorrow" and "today" resolved at request time relative to local timezone

---

## 10. Telegram Bot Integration Strategy

**Library:** `python-telegram-bot` v13.x (sync, confirmed)

> **Confirmed:** v13 synchronous polling model is used for Phase 1. Migration to v20 async in Phase 2 only requires rewriting `bot.py` — all other modules remain unchanged.

**Polling approach:**
- `Updater.start_polling()` with `idle()` — no webhooks needed
- The library handles reconnections automatically
- Only process messages from whitelisted Telegram user IDs (reject others silently or with a brief message)

**Message handling:**
- Single `message_handler` function receives all text messages
- Delegates to `commands.py` for parsing
- Returns plain-text replies (no Markdown needed for Phase 1, but can be added easily)

---

## 11. Scheduler / Reminder Strategy (Later Phases)

> Skip in Phase 1. Notes for planning:

- Phase 2: Use `APScheduler` (lightweight, in-process job scheduler) to push daily morning summaries to Telegram at a configured time
- Phase 2: "remind me 30 mins before" can be stored as a simple list in a JSON file, checked by the scheduler
- Phase 3: Persistent reminders stored in a lightweight SQLite DB if the JSON list grows

---

## 12. Recommended Phased Roadmap

### Phase 0 — Setup / Preparation (Before coding)
- [ ] Create Telegram bot via BotFather → save token
- [ ] Create GCP project, enable Calendar API, download `credentials.json`
- [ ] Note all 6 Calendar IDs from Google Calendar settings
- [ ] Find SungHwan's Telegram User ID
- [ ] Set up Python virtual environment on Windows
- [ ] Initialize Git repo → add `.gitignore` (excluding all secrets)
- [ ] Run first OAuth flow manually to generate `token.json`

### Phase 1 — Minimum Working MVP
- [ ] `config.py` — load all config/env values
- [ ] `calendar_client.py` — auth, list events for a date range, insert event
- [ ] `commands.py` — parse `today`, `tomorrow`, `add` commands
- [ ] `utils.py` — date math, event formatting for Telegram reply
- [ ] `bot.py` — Telegram polling loop, whitelist check, dispatch
- [ ] Manual end-to-end test: send all 3 commands, verify GCal results

### Phase 2 — Useful Daily Operation
- [ ] Morning daily summary (push at 8am via APScheduler)
- [ ] Multi-user support (JeeYoung added to whitelist, per-user settings)
- [ ] Event deletion (`delete` command)
- [ ] Event editing (`edit` or `reschedule`)
- [ ] `week` command — list this week's events
- [ ] Error message improvement and help command (`/help`)

### Phase 3 — Future Enhancements
- [ ] Natural language parsing (LLM integration, optional)
- [ ] Recurring events
- [ ] Per-person reminders
- [ ] Migrate to Telegram webhooks if running on a server
- [ ] Deploy to a VPS or cloud function for reliability

---

## 13. Implementation Order (Step-by-Step Build Sequence)

1. **Create project folder + venv + `.gitignore`**
2. **Write `config.py`** — load `.env` and `config.json`, expose as typed constants
3. **Write `calendar_client.py`** — auth only first, then `list_events()`, then `add_event()`
4. **Test GCal functions in isolation** (small test script, not bot yet)
5. **Write `utils.py`** — date parsing (`today`, `tomorrow`, `DD-MM-YYYY`, day-name shortcuts `Mon`–`Sun`, `HH:MM-HH:MM`), reply formatting
6. **Write `commands.py`** — parse text → return command dict or error
7. **Test `commands.py` with sample strings** (unit test or REPL)
8. **Write `bot.py`** — minimal polling loop + whitelist + dispatch to commands + GCal + reply
9. **End-to-end test** from Telegram
10. **Write `run.bat`** — simple Windows launcher with venv activation

---

## 14. Testing Strategy

### Unit Tests (manual/REPL is fine for Phase 1)
- `commands.py` — test parsing of all valid and invalid inputs
- `utils.py` — test date arithmetic (today, tomorrow, specific dates), time range parsing
- `calendar_client.py` — test with a "test" calendar before using real family calendars

### Integration Test
- Start the bot, send `today` → verify reply matches GCal UI
- Send `add SungHwan test-event tomorrow 10:00-11:00` → verify event appears in Google Calendar
- Send `tomorrow` → verify the new event appears in the reply

### Regression Safety
- Keep a hardcoded set of sample command strings and expected parse outputs
- Run these before any changes to `commands.py`

> No formal test framework required in Phase 1. A `test_commands.py` with `assert` statements is sufficient.

---

## 15. Risks / Failure Points / Edge Cases

| Risk | Mitigation |
|------|-----------|
| OAuth token expiry | `google-auth` auto-refreshes; catch `RefreshError` and warn via Telegram |
| Telegram API timeout / network drop | `python-telegram-bot` retries automatically; log errors |
| Ambiguous calendar name (e.g., `you` matching `YounHa` and `YounHo`) | Require exact name match; reply with list of valid names on mismatch |
| Date parsing ambiguity | Enforce strict `DD-MM-YYYY` format; reject anything else with a usage hint |
| Time zone bugs | Always set timezone explicitly in every GCal API call; never use naive datetimes |
| Windows PC goes to sleep | Control Panel → Power Options → set sleep to "Never" while plugged in; or use `powercfg /change standby-timeout-ac 0` |
| Bot token or credentials leaked to git | Enforce `.gitignore` strictly; use pre-commit hook if sharing the repo |
| Unauthorized Telegram user | Whitelist check is first thing in handler; log rejected user IDs |
| GCal API quota | Free tier allows 1M requests/day — no concern for family use |

---

## 16. Deployment / Runtime on Windows

- **Run method (Phase 1):** Double-click `run.bat` or run `python bot.py` in a terminal with venv activated; keep terminal window open
- **Background execution (Phase 1):** Use `pythonw bot.py` to run without a terminal window, or use `start /B python bot.py` in the batch script
- **Keep PC awake:** Control Panel → Power Options → set all sleep timers to "Never" while plugged in
  - Or via command: `powercfg /change standby-timeout-ac 0`
- **Auto-start on boot (Phase 2):** Register as a Windows Task Scheduler task (trigger: on log-on, action: run `run.bat`)
- **Logs:** Redirect stdout/stderr to `molly.log` in the project folder; include timestamps
- **Python version:** 3.10+ recommended; use `python` (not `python3`) on Windows
- **Virtual environment:** Use `venv`; activate with `.venv\Scripts\activate` on Windows
- **File paths:** Use `pathlib.Path` throughout the code — never hardcode backslashes

---

## 17. Security Considerations

- **Whitelist Telegram User IDs** — reject any message not from authorized users; log the attempt
- **Never commit secrets** — `.env`, `credentials.json`, `token.json` all in `.gitignore`
- **Do not store secrets in `config.json`** — config.json should be safe to commit if needed
- **OAuth consent screen** — set app to "Testing" mode in GCP; add only the dedicated Gmail as a test user
- **No inbound ports open** — polling model means the Mac makes outbound calls only; no firewall changes needed
- **Token file permissions** — On Windows, ensure these files are in a folder accessible only to your user account; avoid storing in shared or publicly accessible locations

---

## 18. Suggested Acceptance Criteria for Phase 1

- [ ] Sending `today` returns a formatted list of today's events across all 6 calendars (or "No events today")
- [ ] Sending `tomorrow` returns tomorrow's events correctly
- [ ] Sending `add YounHa tennis tomorrow 17:00-18:00` creates an event in the YounHa calendar visible in Google Calendar UI
- [ ] Messages from non-whitelisted Telegram users are silently ignored (or get a brief rejection)
- [ ] Bot recovers from a Telegram network error without crashing
- [ ] Bot runs for 24 hours without manual intervention
- [ ] All secrets are absent from the git repository

---

## Proposed Folder Structure

OS-neutral notation. On Windows this is `C:\Users\SungHwan\Desktop\Molly\`; all files sit flat at the root — no nested subdirectory.

```
<project_root>/
├── .env                    # TELEGRAM_BOT_TOKEN (never commit)
├── .gitignore
├── config.json             # Calendar IDs, timezone, authorized user IDs
├── credentials.json        # GCP OAuth client credentials (never commit)
├── token.json              # OAuth refresh token, auto-generated (never run)
├── requirements.txt        # python-telegram-bot, google-api-python-client, python-dotenv
├── run.bat                 # Windows start script (activates venv, runs bot.py)
├── bot.py                  # Entry point, Telegram polling loop
├── commands.py             # Text parser → command dict
├── calendar_client.py      # All GCal API calls
├── config.py               # Load config.json + .env
├── utils.py                # Date math (DD-MM-YYYY, day names), reply formatting
├── tests/
│   ├── test_commands.py    # Parse tests
│   └── test_utils.py       # Date/time tests
└── molly.log               # Runtime log (gitignored)
```

---

## Minimal Command List for Phase 1

| Command | Example | Action |
|---------|---------|--------|
| `today` | `today` | List all events today across all calendars |
| `tomorrow` | `tomorrow` | List all events tomorrow across all calendars |
| `add <calendar> <title> <date> <time>` | `add YounHa tennis tomorrow 17:00-18:00` | Add event to named calendar |
| *(implicit)* | Any unrecognized input | Reply with usage help |

**Valid calendar names (case-insensitive):** `SungHwan`, `JeeYoung`, `YounHa`, `HaNeul`, `YounHo`, `Family`

**Valid date formats (British style):**
- `today`, `tomorrow`, `DD-MM-YYYY` (e.g., `15-04-2026`), and day-name shortcuts `Mon`–`Sun`
- Day-name shortcuts: `Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`, `Sun` → resolved to the *next occurrence* of that weekday (if today is Tuesday and you say `Thu`, it means this Thursday)

> **Assumption:** Day-name shortcuts always refer to within the next 7 days. If the named day is today, it refers to today.

**Valid time formats:**
- `HH:MM-HH:MM` (e.g., `17:00-18:00`)
- `HH:MM` (start time only, default 1-hour duration)

---

## Developer Setup Checklist (Day 1)

- [ ] Install Python 3.10+ and confirm `python --version` in PowerShell
- [ ] Navigate to `C:\Users\SungHwan\Desktop\Molly` and initialize git: `git init`
- [ ] Create `.gitignore` including: `.env`, `credentials.json`, `token.json`, `molly.log`, `__pycache__/`, `.venv/`
- [ ] Create virtual environment: `python -m venv .venv` then `.venv\Scripts\activate`
- [ ] Create Telegram bot via @BotFather → save token to `.env`
- [ ] Create GCP project → enable Calendar API → create OAuth Desktop credentials → download `credentials.json`
- [ ] Open each of the 6 Google Calendars in the browser → copy Calendar ID → paste into `config.json`
- [ ] Find your Telegram User ID → add to `config.json` whitelist
- [ ] Install dependencies: `pip install python-telegram-bot==13.15 google-api-python-client google-auth-oauthlib python-dotenv`
- [ ] Run the OAuth flow once manually (small test script) → confirm `token.json` is generated
- [ ] Confirm you can list events from one calendar in a Python REPL before writing the bot

---

## 5 Most Important Implementation Decisions

1. **Use `python-telegram-bot` v13 (sync) not v20 (async)** — v20 requires `asyncio` patterns that add complexity for a solo builder with no async experience. Migrate to v20 in Phase 2 if needed.
2. **Whitelist by Telegram User ID, not username** — Usernames can be changed; User IDs are permanent. This is the correct and simplest security model.
3. **Require exact calendar name in `add` command** — Do not attempt fuzzy or partial matching in Phase 1. Ambiguity is a source of bugs. Enforce a fixed valid-name list and return an error with the valid names listed.
4. **Always use timezone-aware datetimes** — Never use Python's naive `datetime`. Set timezone from config and apply it to every GCal API call. Timezone bugs are silent and hard to debug.
5. **Keep the main loop (`bot.py`) as thin as possible** — All logic goes into the other modules. `bot.py` should only receive a message, call `commands.parse()`, call the right `calendar_client` function, and send a reply.

---

## Recommended Build Order

1. Project scaffolding (folders, venv, gitignore, requirements.txt)
2. `config.py` — loads all settings
3. `calendar_client.py` — OAuth + list events + add event (tested standalone)
4. `utils.py` — date parsing + reply formatting (tested standalone)
5. `commands.py` — text parser (tested standalone)
6. `bot.py` — wire everything together with Telegram polling
7. `run.bat` — Windows start script (venv activation + `python bot.py`)
8. End-to-end acceptance test from Telegram

---

## The Biggest Thing to Avoid

> **Do not try to support natural language or "smart" parsing in Phase 1.**

The temptation will be to make `add YounHa tennis next Thursday at 5pm for an hour` work from the very beginning. Resist it. Each variation you support multiplies the edge cases you need to handle. The semi-structured format (`add <calendar> <title> <date> <time>`) is fast to type on mobile, predictable, and bug-free to parse. Make it work reliably first. Natural language is Phase 3 at the earliest.
