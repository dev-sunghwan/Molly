# OpenClaw Scheduling Fast Path

## 목표

일정 관련 요청에서는 OpenClaw가 범용 비서처럼 넓게 탐색하지 않고, 가능한 한 빨리 Molly Core deterministic 실행으로 들어가게 한다.

핵심 경로는 다음과 같다.

`Telegram -> OpenClaw scheduling mode -> Molly fast-path CLI -> Molly Core -> Local calendar DB`

## 왜 필요한가

기존 Python Molly bot은 빨랐지만 표현력이 제한적이었다.  
현재 OpenClaw 중심 구조는 유연하지만, 일정 요청에서도 memory search / file read 같은 범용 도구 사용으로 응답 지연이 생길 수 있다.

따라서 일정 요청은 별도의 fast path로 다루는 것이 맞다.

## 원칙

일정 관련 요청에서는 OpenClaw가:

1. 일정 의도를 구조화한다
2. 정보가 충분하면 바로 Molly fast-path CLI를 호출한다
3. 정보가 부족하면 짧게 clarification 한다
4. 불필요한 memory/file tool 사용은 피한다

## fast-path CLI

- `scripts/molly_schedule_action.py create`
- `scripts/molly_schedule_action.py view`
- `scripts/molly_schedule_action.py search`
- `scripts/molly_schedule_action.py delete`
- `scripts/molly_schedule_action.py update`

이 경로는 OpenClaw가 긴 stdin JSON 조립 대신 명시적 argv 명령을 만들 수 있게 해준다.

## OpenClaw scheduling 지침 초안

일정 관련 요청을 처리할 때는 아래 규칙을 우선한다.

- memory search를 기본적으로 하지 않는다
- file read/write를 기본적으로 하지 않는다
- 요청 정보가 완전하면 즉시 Molly CLI를 실행한다
- 정보가 모자라면 필요한 질문만 1회씩 짧게 한다
- 실행 결과는 간단한 자연어로 사용자에게 보고한다

## 기대 효과

- 일정 요청 응답 속도 개선
- OpenClaw reasoning 비용 축소
- Molly Core deterministic safety 유지
- 일반 대화와 일정 실행의 역할 분리 강화
