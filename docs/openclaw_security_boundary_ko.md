# OpenClaw Security Boundary

## 목적

이 문서는 Molly를 OpenClaw 중심으로 운영할 때 Telegram production 경로와 Slack admin/dev 경로의 권한을 분리하기 위한 기준이다.

목표는 세 가지다.

- Telegram 가족 사용 경로를 빠르고 좁게 유지한다.
- Slack 개발/관리 경로가 Telegram production 응답을 막지 않게 한다.
- LLM/OpenClaw가 직접 DB나 Python 코드를 실행하는 구조가 되지 않게 한다.

## 채널 역할

### Telegram

Telegram은 production family interface다.

허용되는 역할:

- 가족 일정 조회
- 가족 일정 추가
- 명확한 일정 수정/삭제
- 부족한 정보에 대한 짧은 clarification
- Gmail 후보 확인 같은 사용자 확인 흐름

제한되는 역할:

- repo 파일 읽기/쓰기
- 로그 대량 조회
- 테스트 실행
- OpenClaw 설정 변경
- Google sync worker 직접 제어
- 임의 shell/Python/SQL 실행

Telegram agent는 scheduling fast path만 우선 사용한다.

### Slack

Slack은 admin/debug/development interface다.

허용되는 역할:

- commands journal 조회
- Google sync outbox/backlog 조회
- 실패 요청 원인 확인
- 문서/테스트/로그 기반 디버깅
- 명시적인 운영 명령 실행

제한되는 역할:

- 일반 대화나 모호한 자연어에서 production calendar mutation 바로 실행
- request id 없는 mutation 실행
- 사용자가 명시하지 않은 delete/update/move 실행
- secret 출력
- `.env`, `token.json`, `credentials.json`, Slack/Telegram/Google token 읽기

Slack agent는 넓게 읽고 분석할 수 있지만, production mutation은 명시적 command로만 허용한다.

## Molly 실행 경계

LLM/OpenClaw는 실행기가 아니다.

LLM/OpenClaw가 할 수 있는 일:

- 자연어를 구조화한다.
- clarification 질문을 만든다.
- Molly CLI 인자를 준비한다.
- 실행 결과를 사용자에게 설명한다.

LLM/OpenClaw가 하면 안 되는 일:

- Python 코드를 직접 실행해 DB를 수정한다.
- SQL을 직접 생성해 local DB에 쓴다.
- Google Calendar API를 직접 호출한다.
- token/credential 파일을 읽거나 출력한다.

실제 일정 변경은 항상 Molly Core가 수행한다.

## Request ID 규칙

모든 Telegram/Slack scheduling 요청은 stable request id를 가져야 한다.

권장 형식:

- Telegram: `telegram:<chat_id>:<message_id>`
- Slack: `slack:<channel_id>:<ts>`

mutation 요청에는 반드시 아래 인자를 전달한다.

```bash
--request-id "<stable_request_id>" \
--source telegram|slack \
--source-message-id "<message_id_or_ts>" \
--source-user-id "<sender_id>" \
--source-channel-id "<chat_or_channel_id>"
```

`MOLLY_REQUIRE_REQUEST_ID_FOR_MUTATIONS=1`을 켜면 request id 없는 mutation은 Molly가 reject한다.

## Source 정책

### Telegram source

Telegram source는 production scheduling 요청으로 취급한다.

허용:

- `view`
- `search`
- `create`
- 명확한 `update`
- 명확한 `delete`
- 명확한 `move`

필수 조건:

- stable request id
- calendar key가 명확하거나 clarification 완료
- 날짜/시간/대상 이벤트가 충분히 특정됨

### Slack source

Slack source는 admin/dev 요청으로 취급한다.

허용:

- journal/outbox 상태 조회
- dry-run
- test/debug command
- 명시적 admin command

production mutation 조건:

- 사용자가 명시적으로 calendar mutation을 요청해야 한다.
- stable request id가 있어야 한다.
- Slack agent가 추측으로 calendar key/date/title을 채우면 안 된다.
- delete/update/move는 대상이 하나로 특정되지 않으면 실행하지 않는다.

## Tool 권한 기준

Telegram agent:

- 허용: Molly scheduling CLI 실행
- 제한: repo 파일 탐색, 로그 대량 조회, write tool, config 변경
- 권장 context: calendar key map, request id 규칙, Molly CLI examples

Slack dev agent:

- 허용: repo read, tests, logs, admin 조회 CLI
- 제한: secret files, production mutation without explicit command
- 권장 context: architecture docs, phase log, admin commands

## Production 연결 전 체크리스트

1. Telegram agent가 모든 mutation CLI에 `--request-id`를 붙이는지 확인한다.
2. Telegram agent가 `--source telegram`을 붙이는지 확인한다.
3. Slack agent가 `--source slack`을 붙이는지 확인한다.
4. 같은 Telegram message id로 create를 두 번 실행했을 때 두 번째 실행이 replay result를 반환하는지 확인한다.
5. `MOLLY_REQUIRE_REQUEST_ID_FOR_MUTATIONS=1`을 켠 dry-run 환경에서 request id 없는 mutation이 reject되는지 확인한다.
6. secret 파일을 읽거나 출력하지 않는지 확인한다.
7. Telegram latency가 Slack/debug 작업과 독립적인지 확인한다.

## Rollback

문제가 생기면 다음 순서로 되돌린다.

1. `MOLLY_REQUIRE_REQUEST_ID_FOR_MUTATIONS=0`으로 둔다.
2. live OpenClaw config 변경을 이전 백업으로 되돌린다.
3. Google sync worker가 켜져 있다면 중지한다.
4. local DB는 source of truth로 유지한다.

## 현재 상태

현재 repo 기준으로는 다음 기반이 준비되어 있다.

- commands journal
- request replay guard
- stable request id mutation gate flag
- Google sync outbox
- Google sync worker baseline
- Google event mapping baseline

아직 live OpenClaw Telegram/Slack runtime 설정은 이 문서 기준으로 직접 변경하지 않았다.
