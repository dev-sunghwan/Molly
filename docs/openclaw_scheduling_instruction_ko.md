# OpenClaw Scheduling Instruction Draft

## 목적

이 문서는 Molly가 텔레그램에서 **일정 관련 요청**을 받을 때, 일반 대화 모드가 아니라 **빠른 scheduling mode**로 동작하도록 유도하기 위한 운영 지침 초안이다.

핵심 목표는:

- 불필요한 추론과 도구 사용을 줄이고
- 필요한 정보만 확인한 뒤
- 가능한 한 빨리 Molly Core deterministic 실행으로 넘기는 것

## 적용 범위

다음과 같은 요청은 scheduling mode로 본다.

- 일정 추가
- 오늘 / 내일 / 특정일 일정 조회
- upcoming / next 일정 조회
- 키워드 검색
- 일정 수정
- 일정 삭제

예:

- "내일 오후 6시에 윤하 테니스 넣어줘"
- "오늘 일정 보여줘"
- "하늘 수영 일정 찾아줘"
- "윤하 테니스 6시로 바꿔줘"
- "가족 Costco 일정 지워줘"

## 기본 규칙

일정 요청에서는 아래 규칙을 우선한다.

1. memory search를 기본적으로 하지 않는다
2. file read/write를 기본적으로 하지 않는다
3. 요청 정보가 충분하면 바로 Molly fast-path CLI를 실행한다
4. 정보가 부족하면 필요한 질문만 짧게 한다
5. 실행 결과는 짧고 분명하게 보고한다
6. routine calendar request는 Molly CLI 한 번 실행 후 `message`를 그대로 반환한다
7. create/update/delete/move는 가능한 한 canonical `command`가 아니라 명시적 fast-path subcommand를 쓴다

즉 scheduling mode에서는:

- "더 많이 생각하는 것"보다
- "충분히 안전하게 빨리 실행하는 것"

이 우선이다.

## Structured JSON 경계

OpenClaw/LLM은 Molly Core에 직접 Python, shell, SQL, DB write 지시를 넘기면 안 된다.

허용되는 출력은 Molly가 정의한 scheduling command JSON 또는 그 JSON을 인자로 만드는 fast-path CLI 호출뿐이다.

Molly Python validator가 실행 가능 여부를 최종 결정한다. 다음과 같은 필드는 요청 JSON에 포함하지 않는다.

- `python`
- `shell`
- `sql`
- `exec`
- `eval`
- `tool_call`
- `function_call`
- `command`

허용 action은 다음으로 제한한다.

- `create_event`
- `view`
- `search`
- `delete_event`
- `move_event`
- `update_event`

알 수 없는 action이나 action별 schema에 없는 field는 Molly Core에서 reject된다.

## Clarification 규칙

아래 정보가 없으면 짧게 되묻는다.

- 누구 캘린더인지 불명확함
- 날짜가 불명확함
- 시작/종료 시간이 불충분함
- 수정/삭제 대상이 여러 개라 특정이 안 됨

질문은 한 번에 필요한 것만 묻는다.

좋은 예:

- "어느 가족 구성원 캘린더에 넣을까요?"
- "종료 시간도 알려주세요."
- "같은 이름 일정이 여러 개 있어요. 날짜를 알려주세요."

나쁜 예:

- 장황한 설명
- 이미 알 수 있는 정보를 다시 묻기
- 실행 전 불필요한 메모리 탐색

## 도구 사용 우선순위

일정 요청에서는 다음 우선순위를 따른다.

1. Molly fast-path CLI
2. 짧은 clarification
3. 그 외 도구는 정말 필요한 경우에만

기본 명령 표면은 다음이다.

```bash
./.venv/bin/python scripts/molly_schedule_action.py command --text "today" --request-id "<stable-source-message-id>"
./.venv/bin/python scripts/molly_schedule_action.py command --text "week" --request-id "<stable-source-message-id>"
./.venv/bin/python scripts/molly_schedule_action.py create ... --request-id "<stable-source-message-id>"
./.venv/bin/python scripts/molly_schedule_action.py view ... --request-id "<stable-source-message-id>"
./.venv/bin/python scripts/molly_schedule_action.py search ... --request-id "<stable-source-message-id>"
./.venv/bin/python scripts/molly_schedule_action.py update ... --request-id "<stable-source-message-id>"
./.venv/bin/python scripts/molly_schedule_action.py delete ... --request-id "<stable-source-message-id>"
```

Routine scheduling request에서는 사전 진단용 `ps`, `status`, 파일 읽기, memory search, docs lookup을 하지 않는다. 이런 작업은 Slack/admin debug에서만 수행한다.

## Request ID 규칙

Telegram/Slack/OpenClaw에서 들어온 scheduling 요청은 가능한 한 항상 stable request id를 Molly CLI에 전달한다.

원칙:

- LLM이 `request_id`를 새로 만들거나 추측하지 않는다.
- OpenClaw gateway/runtime metadata의 message id, chat/channel id, thread id 등을 조합해 stable id를 만든다.
- 같은 사용자 메시지를 재처리할 때 같은 `request_id`가 전달되어야 한다.
- mutation 요청에는 특히 반드시 `--request-id`를 붙인다.

권장 형식:

- Telegram: `telegram:<chat_id>:<message_id>`
- Slack: `slack:<channel_id>:<ts>`
- OpenClaw internal retry: 원본 Telegram/Slack id를 그대로 재사용

추가 metadata가 있으면 함께 전달한다.

```bash
--request-id "telegram:<chat_id>:<message_id>" \
--source telegram \
--source-message-id "<message_id>" \
--source-user-id "<telegram_user_id>" \
--source-channel-id "<chat_id>"
```

`MOLLY_REQUIRE_REQUEST_ID_FOR_MUTATIONS=1`이 켜진 환경에서는 create/update/delete/move 같은 mutation 요청이 stable request id 없이 들어오면 Molly가 실행하지 않고 reject한다.

## 액션별 실행 예시

### 1. 일정 추가

```bash
./.venv/bin/python scripts/molly_schedule_action.py create \
  --calendar younha \
  --title "윤하 테니스" \
  --date 2026-04-17 \
  --start 18:00 \
  --end 19:00 \
  --raw-input "내일 오후 6시에 윤하 테니스 넣어줘" \
  --request-id "telegram:<chat_id>:<message_id>" \
  --source telegram \
  --source-message-id "<message_id>"
```

### 2. 일정 조회

simple read는 canonical command passthrough를 우선한다.

```bash
./.venv/bin/python scripts/molly_schedule_action.py command --text "today" \
  --request-id "telegram:<chat_id>:<message_id>" \
  --source telegram
```

```bash
./.venv/bin/python scripts/molly_schedule_action.py command --text "week" \
  --request-id "telegram:<chat_id>:<message_id>" \
  --source telegram
```

```bash
./.venv/bin/python scripts/molly_schedule_action.py command --text "upcoming Family 10" \
  --request-id "telegram:<chat_id>:<message_id>" \
  --source telegram
```

구조화된 view bridge는 날짜 지정이나 surface 제약이 있을 때 보조적으로 쓴다.

```bash
./.venv/bin/python scripts/molly_schedule_action.py view \
  --scope date \
  --date 2026-04-18 \
  --raw-input "4월 18일 일정 보여줘" \
  --request-id "telegram:<chat_id>:<message_id>" \
  --source telegram
```

### 3. 일정 검색

```bash
./.venv/bin/python scripts/molly_schedule_action.py search \
  --query "Beavers" \
  --raw-input "Beavers 일정 찾아줘" \
  --request-id "telegram:<chat_id>:<message_id>" \
  --source telegram
```

### 4. 일정 수정

```bash
./.venv/bin/python scripts/molly_schedule_action.py update \
  --calendar younha \
  --title "Tennis" \
  --date 2026-04-17 \
  --start 19:00 \
  --end 20:00 \
  --raw-input "윤하 테니스 내일 7시로 바꿔줘" \
  --request-id "telegram:<chat_id>:<message_id>" \
  --source telegram
```

### 5. 일정 삭제

```bash
./.venv/bin/python scripts/molly_schedule_action.py delete \
  --calendar family \
  --title "Costco" \
  --date 2026-04-18 \
  --raw-input "가족 Costco 일정 지워줘" \
  --request-id "telegram:<chat_id>:<message_id>" \
  --source telegram
```

## 응답 스타일

일정 요청의 응답은:

- 짧고
- 실행 여부가 분명하고
- 다음 행동이 필요하면 그것만 알려준다

좋은 예:

- "윤하 캘린더에 내일 18:00–19:00 테니스 일정을 추가했어요."
- "오늘 일정은 3개예요."
- "어느 캘린더에서 지울까요?"

나쁜 예:

- 쓸데없이 장황한 배경 설명
- 내부 추론 노출
- 실행과 무관한 생활 조언 섞기

## 권장 적용 방식

이 초안은 `SOUL.md` 전체를 크게 바꾸기보다, scheduling 관련 운영 규칙으로 요약해 반영하는 것이 좋다.

권장 방향:

- SOUL에는 "일정 요청은 빠르고 분명하게 처리한다" 수준으로 짧게 반영
- 자세한 실행 규칙은 별도 운영 문서로 유지

그렇게 하면 Molly의 캐릭터는 유지하면서도 scheduling 속도는 개선할 수 있다.
