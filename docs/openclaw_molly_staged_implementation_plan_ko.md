# OpenClaw 중심 Molly 단계별 구현 계획

## 목표 구조

Molly의 목표 runtime 구조는 OpenClaw를 Telegram/Slack gateway로 유지하면서, Molly Python 코드를 deterministic business logic 경계로 사용하는 것이다.

```text
Telegram / Slack
-> OpenClaw Gateway
-> structured command
-> SQLite commands journal
-> Python parser / validator
-> Molly Core executor
-> local_calendar.db
-> async Google Calendar sync
-> Google Calendar
```

핵심 원칙:

- Telegram은 가족 production interface다.
- Slack은 admin, debug, development interface다.
- LLM/OpenClaw 출력은 structured JSON이어야 한다.
- Python validator/executor가 실행 가능 여부를 결정한다.
- 모든 inbound request는 parsing/execution 전에 SQLite에 저장한다.
- local SQLite calendar DB가 source of truth다.
- Google Calendar는 asynchronous sync target이다.
- Google Calendar sync 실패나 지연은 Telegram 사용자 응답을 막지 않는다.

## Stage 0. Runtime 경계 문서화

현재 운영 경로를 문서화한다. `bot.py`는 repo에 남아 있지만 현재 production Telegram 대화는 OpenClaw gateway를 통해 처리되는 것으로 본다.

Likely files:

- `docs/architecture_runtime_current_ko.md`
- `docs/openclaw_molly_staged_implementation_plan_ko.md`

Expected behaviour change:

- 없음.

Risks:

- 문서가 실제 OpenClaw 설정과 어긋나면 이후 구현 기준이 흔들릴 수 있다.

Test plan:

- `openclaw status`와 process list로 gateway, Telegram/Slack agent, reminder worker 상태를 확인한다.
- secret 파일은 열거나 출력하지 않는다.

Rollback plan:

- 문서 commit revert.

## Stage 1. Commands Journal 스키마 추가

모든 inbound request를 parsing 전에 저장할 수 있는 DB table과 최소 API를 추가한다. 이 stage에서는 production path에 연결하지 않는다.

Likely files:

- `state_store.py`
- `tests/test_state_store.py`

Expected behaviour change:

- 없음. 저장 API와 schema만 추가된다.

Risks:

- 기존 `data/molly_state.db`에 새 table이 추가된다.
- schema를 너무 빨리 확정하면 이후 migration 비용이 생길 수 있다.

Test plan:

- `state_store.init_db()`가 새 table을 만든다.
- inbound command 저장/조회가 동작한다.
- 같은 `request_id` 저장은 기존 row를 재사용한다.
- status update가 동작한다.

Rollback plan:

- 코드 revert.
- 추가된 table은 기존 runtime에서 참조하지 않으므로 남아 있어도 production 영향은 없다.

## Stage 2. Molly CLI 진입점에 Journal 연결

OpenClaw가 호출하는 Molly CLI가 command를 실행하기 전에 먼저 DB에 request를 저장한다.

Likely files:

- `scripts/molly_schedule_action.py`
- `scripts/molly_core_execute.py`
- `state_store.py`
- `tests/test_molly_schedule_action_script.py`
- `tests/test_molly_core_requests.py`

Expected behaviour change:

- CLI를 통한 scheduling 요청이 실행 전에 `commands` table에 저장된다.
- 사용자 응답 내용은 기존과 동일해야 한다.

Risks:

- CLI 실행 시간이 약간 증가한다.
- SQLite lock 가능성이 생긴다.
- OpenClaw가 안정적인 request id를 넘기기 전까지 retry dedupe가 제한된다.

Test plan:

- `molly_schedule_action.py command --text today` 실행 시 command row 생성 확인.
- invalid command도 row가 남는지 확인.
- success/failure status update 확인.
- 기존 CLI JSON output이 깨지지 않는지 확인.

Rollback plan:

- journal write를 feature flag로 감싼다.
- 문제 발생 시 `MOLLY_COMMAND_JOURNAL_ENABLED=0`으로 비활성화한다.

## Stage 3. Structured JSON Boundary 정리

OpenClaw/LLM 출력 형식을 하나의 Molly command JSON schema로 통일한다.

Likely files:

- `molly_core_requests.py`
- `intent_models.py`
- `telegram_extraction.py`
- `openclaw_molly_bridge.py`
- `docs/openclaw_scheduling_instruction_ko.md`
- `tests/test_molly_core_requests.py`

Expected behaviour change:

- OpenClaw는 실행용 structured JSON을 만든다.
- Molly Python은 JSON을 검증한 뒤 safe command만 실행한다.
- malformed JSON, unknown action, missing required fields는 실행하지 않는다.

Risks:

- OpenClaw prompt와 Python validator가 일시적으로 불일치할 수 있다.
- 자연어 UX가 일시적으로 딱딱해질 수 있다.

Test plan:

- valid create/view/search/delete/update JSON 테스트.
- malformed JSON 테스트.
- unknown action reject 테스트.
- dangerous extra field reject/ignore 정책 테스트.

Rollback plan:

- 기존 canonical command path를 유지한다.
- structured JSON path만 feature flag 처리한다.

## Stage 4. Command Lifecycle 상태 머신 추가

저장된 command가 어디서 실패했는지 추적할 수 있게 상태 전이를 정리한다.

Likely files:

- `state_store.py`
- `scripts/molly_schedule_action.py`
- `scripts/molly_core_execute.py`
- `tests/test_state_store.py`

Expected behaviour change:

- command row가 `received`, `parsing`, `validated`, `executing`, `executed`, `rejected`, `failed`, `needs_clarification` 상태를 갖는다.

Risks:

- 상태 전이가 복잡해질 수 있다.
- 예외 처리 누락 시 `executing` 상태로 멈춘 row가 생길 수 있다.

Test plan:

- success path 상태 전이 테스트.
- validation reject 상태 테스트.
- executor exception 상태 테스트.

Rollback plan:

- 상태 업데이트 실패가 사용자 응답을 막지 않도록 단계적으로 연결한다.

## Stage 5. Local DB Source-of-Truth 강화

production calendar mutation은 local calendar DB에 먼저 반영되도록 고정한다.

Likely files:

- `local_calendar_backend.py`
- `calendar_repository.py`
- `molly_core.py`
- `tests/test_local_calendar_backend.py`
- `tests/test_molly_core.py`

Expected behaviour change:

- production backend는 local DB 기준으로 동작한다.
- Google backend direct execution은 legacy/dev 경로로 격하한다.
- `MOLLY_CALENDAR_BACKEND=google`는 `MOLLY_ALLOW_GOOGLE_PRIMARY_BACKEND=1`이 있을 때만 허용한다.
- Google import/sync scripts는 repository primary backend가 아니라 별도 adapter이므로 계속 사용할 수 있다.

Risks:

- `MOLLY_CALENDAR_BACKEND=google`를 사용하던 수동 경로가 영향을 받을 수 있다.

Test plan:

- local create/update/delete/search 테스트.
- Google credentials 없이 core tests 통과 확인.

Rollback plan:

- Google backend 코드는 삭제하지 않는다.
- env로 기존 backend 선택 가능하게 유지한다.

## Stage 6. Google Sync Outbox 추가

Google Calendar sync를 Telegram response path에서 완전히 분리한다.

Status:

- 2026-05-01 baseline 완료.
- 현재 단계는 outbox 적재까지만 포함한다. 실제 Google Calendar 반영 worker는 Stage 7에서 처리한다.

Likely files:

- `state_store.py`
- `config.py`
- `molly_core.py`
- `tests/test_state_store.py`
- `tests/test_google_sync_outbox.py`

Expected behaviour change:

- local mutation 후 Google sync 작업이 pending outbox row로 기록된다.
- Telegram 응답은 local DB 성공 기준으로 즉시 반환된다.

Risks:

- outbox 중복 생성 가능성.
- update/delete sync 정책 복잡성.

Test plan:

- local create 시 outbox row 생성.
- Google 장애 상태에서도 Telegram/CLI command 성공.
- sync worker dry-run 테스트.

Rollback plan:

- outbox 생성 feature flag.
- worker 중지 시 Google 반영만 멈추고 local DB는 유지된다.

## Stage 7. Google Sync Worker 구현

pending outbox를 처리하는 별도 worker를 추가한다.

Status:

- 2026-05-01 baseline 완료.
- `create` outbox row는 Google Calendar에 반영할 수 있다.
- `update`, `delete`, `move`, `delete_series`는 아직 위험도가 높아 `unsupported`로 기록한다.
- 2026-05-06 production systemd timer 연결 완료.
- 저사양 머신을 고려해 상주 loop가 아니라 5분 주기 `Type=oneshot` user service로 운영한다.

Likely files:

- `scripts/run_google_sync_worker.py`
- `calendar_sync.py`
- `state_store.py`
- `deploy/systemd/molly-google-sync-worker.service`
- `deploy/systemd/molly-google-sync-worker.timer`
- `tests/test_calendar_sync.py`
- `tests/test_google_sync_worker.py`

Expected behaviour change:

- Google Calendar sync가 background에서 실행된다.
- Google API 장애 시 retry 가능하다.
- `--dry-run`으로 pending outbox를 claim하지 않고 미리 확인할 수 있다.

Risks:

- Google API rate limit.
- worker 중복 실행 시 같은 outbox row를 동시에 처리할 수 있다.
- Google insert 성공 후 local 저장 전 crash하면 duplicate 가능성이 있다.

Test plan:

- fake Google backend로 create sync 테스트.
- retry/backoff 테스트.
- duplicate worker claim 방지 테스트.

Rollback plan:

- systemd service stop.
- outbox rows는 local DB에 남아 나중에 재처리 가능하다.

## Stage 8. Idempotency / Duplicate 방지

OpenClaw retry, Telegram duplicate delivery, Slack 재실행으로 인한 중복 생성을 줄인다.

Status:

- 2026-05-01 Google sync idempotency baseline 완료.
- `google_event_mappings`가 outbox/idempotency key와 Google event id를 저장한다.
- worker는 이미 mapping된 create row를 Google에 다시 insert하지 않고 `done` 처리한다.
- 2026-05-01 local create outbox row에 `local_event_id`를 연결했다.
- 2026-05-01 `executed` 상태의 같은 `request_id`는 저장된 execution result를 재사용한다.
- 2026-05-01 `MOLLY_REQUIRE_REQUEST_ID_FOR_MUTATIONS` flag를 추가했다. 켜면 mutation 요청은 stable request id 없이는 `rejected` 처리된다.
- 2026-05-01 OpenClaw bridge와 scheduling instruction이 stable request id/source metadata를 전달하도록 정리됐다.
- failed/rejected replay 정책과 update/delete propagation은 아직 다음 단계로 남겨둔다.

Likely files:

- `state_store.py`
- `calendar_sync.py`
- `calendar_repository.py`
- `local_calendar_backend.py`
- `molly_core.py`
- `scripts/molly_core_execute.py`
- `scripts/molly_schedule_action.py`
- `openclaw_molly_bridge.py`
- `docs/openclaw_scheduling_instruction_ko.md`
- `config.py`
- `tests/test_state_store.py`
- `tests/test_google_sync_worker.py`
- `tests/test_google_sync_outbox.py`

Expected behaviour change:

- Google sync worker 재시도 시 이미 mapping된 create 작업은 중복 insert하지 않는다.
- Google에 이미 동등한 이벤트가 있으면 mapping을 기록하고 `done` 처리한다.
- local create 후 outbox row가 stable local event id를 보유한다.
- 같은 `request_id`가 이미 실행 완료된 경우 calendar mutation을 반복하지 않는다.
- flag 활성화 시 mutation 요청은 explicit stable request id가 필요하다.
- OpenClaw bridge는 request metadata를 LLM 출력에 의존하지 않고 payload/CLI에 주입한다.

Risks:

- 실제로 같은 시간에 같은 제목의 별도 이벤트를 만들고 싶은 경우 막힐 수 있다.
- 현재 idempotency key는 intent payload 기반이라 local event id 기반 mapping보다 약하다.

Test plan:

- 이미 mapping된 outbox row는 Google insert 호출 없이 `done`.
- Google insert 후 event id를 재조회할 수 있으면 mapping에 저장.
- Google에 같은 이벤트가 이미 있으면 mapping 생성 후 skip.

Rollback plan:

- 먼저 application-level dedupe로 시작하고 DB unique constraint는 나중에 추가한다.

## Stage 9. Telegram / Slack 권한 분리

Telegram production agent와 Slack dev agent의 권한, 모델, 도구를 분리한다.

Status:

- 2026-05-01 repo-side security boundary 문서화 완료.
- 2026-05-01 live Telegram fast / Slack dev workspace `AGENTS.md` instruction 반영 완료.
- secret-bearing OpenClaw config는 읽거나 수정하지 않았다.

Likely files:

- `docs/openclaw_security_boundary_ko.md`
- OpenClaw 설정 문서

Expected behaviour change:

- Telegram은 scheduling fast path만 사용한다.
- Slack은 debug/admin 가능하지만 production mutation은 명시적 command만 허용한다.
- OpenClaw workspace instruction 기준으로 request id/source metadata 전달 규칙이 강화된다.

Risks:

- OpenClaw 설정은 repo 밖에 있을 수 있다.
- 권한을 너무 줄이면 Slack dev workflow가 불편해질 수 있다.

Test plan:

- Telegram create/view latency 확인.
- Slack debug query 확인.
- Slack에서 임의 calendar mutation이 바로 실행되지 않는지 확인.
- OpenClaw security audit 재확인.

Rollback plan:

- OpenClaw config 백업 후 변경한다.
- 문제 발생 시 이전 config로 restore한다.

## Stage 10. Legacy `bot.py` 정리

direct Telegram bot이 production path가 아님을 명확히 한다.

Status:

- 2026-05-05 완료.
- `bot.py`는 기본적으로 disabled이며 `MOLLY_LEGACY_TELEGRAM_BOT_ENABLED=1`일 때만 polling runtime으로 실행된다.
- 기존 single-instance lock과 Telegram polling conflict handling은 유지하고 startup에서 실제로 lock을 획득한다.

Likely files:

- `bot.py`
- `config.py`
- runtime docs

Expected behaviour change:

- 실수로 `bot.py`를 켜서 Telegram polling conflict를 만들 가능성이 줄어든다.
- OpenClaw production path가 기본 Telegram runtime임을 실행 시점에서도 명확히 한다.

Risks:

- emergency fallback으로 `bot.py`를 쓰고 있었다면 불편해질 수 있다.

Test plan:

- 기본 실행 시 명확한 message로 종료.
- env flag를 켜면 기존처럼 동작.

Rollback plan:

- env flag로 즉시 복구 가능하게 구현한다.

## Stage 11. Admin 조회 CLI

Slack admin/debug에서 commands journal과 sync 상태를 안전하게 볼 수 있게 한다.

Status:

- 2026-05-06 완료.
- `scripts/molly_admin.py`가 read-only `summary`, `commands`, `command`, `sync` subcommand를 제공한다.
- command raw text/payload는 기본 출력에서 숨기고, payload 포함 옵션 사용 시 token/secret-like key를 redaction한다.

Likely files:

- 신규 `scripts/molly_admin.py`
- `state_store.py`
- tests

Expected behaviour change:

- 최근 실패 요청, Google sync backlog 확인 가능.

Risks:

- raw payload에 가족 일정 정보가 포함될 수 있다.
- Slack group에 너무 많은 정보가 노출될 수 있다.

Test plan:

- output에 tokens/env/secrets가 없는지 테스트.
- failed commands 조회 테스트.
- sync backlog 조회 테스트.

Rollback plan:

- admin CLI를 Slack agent에서 사용 금지하면 production mutation에는 영향이 없다.

## Stage 12. End-to-End 운영 검증

production에 필요한 최소 시나리오를 실제 흐름 기준으로 검증한다.

Validation scenarios:

- Telegram natural language create
- Telegram missing calendar clarification
- Telegram view today/upcoming
- Telegram duplicate retry
- Slack debug query
- Slack explicit admin command
- Google down 상태에서 Telegram create 성공
- Google sync worker 복구 후 반영
- reminder worker가 local DB 기준으로 알림 전송

Rollback plan:

- worker stop.
- local test event delete.
- Google test event 수동 삭제.
