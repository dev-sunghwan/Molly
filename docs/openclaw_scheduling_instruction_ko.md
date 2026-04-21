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

즉 scheduling mode에서는:

- "더 많이 생각하는 것"보다
- "충분히 안전하게 빨리 실행하는 것"

이 우선이다.

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
./.venv/bin/python scripts/molly_schedule_action.py create ...
./.venv/bin/python scripts/molly_schedule_action.py view ...
./.venv/bin/python scripts/molly_schedule_action.py search ...
./.venv/bin/python scripts/molly_schedule_action.py update ...
./.venv/bin/python scripts/molly_schedule_action.py delete ...
```

## 액션별 실행 예시

### 1. 일정 추가

```bash
./.venv/bin/python scripts/molly_schedule_action.py create \
  --calendar younha \
  --title "윤하 테니스" \
  --date 2026-04-17 \
  --start 18:00 \
  --end 19:00 \
  --raw-input "내일 오후 6시에 윤하 테니스 넣어줘"
```

### 2. 일정 조회

```bash
./.venv/bin/python scripts/molly_schedule_action.py view \
  --scope today \
  --raw-input "오늘 일정 보여줘"
```

```bash
./.venv/bin/python scripts/molly_schedule_action.py view \
  --scope upcoming \
  --calendar family \
  --limit 10 \
  --raw-input "가족 일정 앞으로 10개 보여줘"
```

### 3. 일정 검색

```bash
./.venv/bin/python scripts/molly_schedule_action.py search \
  --query "Beavers" \
  --raw-input "Beavers 일정 찾아줘"
```

### 4. 일정 수정

```bash
./.venv/bin/python scripts/molly_schedule_action.py update \
  --calendar younha \
  --title "Tennis" \
  --date 2026-04-17 \
  --start 19:00 \
  --end 20:00 \
  --raw-input "윤하 테니스 내일 7시로 바꿔줘"
```

### 5. 일정 삭제

```bash
./.venv/bin/python scripts/molly_schedule_action.py delete \
  --calendar family \
  --title "Costco" \
  --date 2026-04-18 \
  --raw-input "가족 Costco 일정 지워줘"
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
