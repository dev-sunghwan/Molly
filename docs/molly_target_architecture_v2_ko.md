# Molly Target Architecture v2

## 한 줄 원칙

`LLM interprets, Molly decides, local store persists, external services sync.`

## 목표

Molly를 다시 단순하게 만든다.

- 자연어 해석은 앞단에 둔다.
- 캘린더 실행 규칙은 Molly core에 둔다.
- 기본 저장 기준은 로컬 캘린더에 둔다.
- Google Calendar와 Gmail은 선택적 adapter로 둔다.

## 레이어별 책임

### 1. Interfaces

- Telegram
- OpenClaw chat surfaces
- 추후 다른 chat surface

역할:
- 사용자 입력 수신
- 결과 전달
- transport metadata 전달

여기서는 비즈니스 로직을 갖지 않는다.

### 2. LLM / NLU frontend

역할:
- 자유 자연어를 Molly canonical command 또는 structured intent로 변환
- 필요한 경우에만 clarification 생성

하지 말아야 할 일:
- 캘린더 상태를 source of truth처럼 판단
- 실행 규칙 보유
- 백엔드 차이 직접 처리

즉, LLM은 interpreter이지 scheduler가 아니다.

### 3. Molly adapters

역할:
- surface별 입력을 Molly core 실행 표면으로 연결
- simple command는 가능한 한 그대로 passthrough
- write 요청은 structured argument bridge 사용 가능

권장 경로:
- simple read: `command` fast path
- structured write: `create/update/delete` fast path
- ambiguous natural language: LLM -> canonical command or intent -> core

### 4. Molly core

역할:
- canonical command vocabulary 정의
- validation / normalization
- deterministic execution
- reminder / audit / policy enforcement

Molly core가 유일한 실행 권한 계층이다.

### 5. Storage

기본:
- local calendar repository

선택:
- Google Calendar sync target
- ICS / CalDAV adapter

기준은 local-first다.

## 권장 데이터 흐름

### A. Simple read path

`user text -> adapter -> canonical Molly command -> Molly core -> local repository -> reply`

예:
- `today`
- `tomorrow`
- `week`
- `upcoming`

이 경로에서는 불필요한 schema translation을 최소화한다.

### B. Structured write path

`user text -> LLM/NLU -> structured intent -> Molly core -> local repository -> optional sync -> reply`

예:
- 일정 생성
- 일정 수정
- 일정 삭제
- 반복 일정 생성

### C. External ingestion path

`Gmail / import source -> candidate extraction -> Molly review/confirm flow -> Molly core -> local repository`

Gmail은 core authority가 아니라 ingestion source다.

## Google Calendar 재연동 원칙

Google Calendar는 다시 붙이는 것이 좋다. 다만 역할은 분명해야 한다.

권장 역할:
- user-facing backup view
- export target
- selective sync peer
- 외부 공유/확인용 surface

비권장 역할:
- Molly 전체의 단일 source of truth
- core validation 우회 실행 계층

## 동기화 단계 제안

### Stage 1

- local calendar를 source of truth로 유지
- Molly에서 발생한 변경을 Google Calendar로 반영
- Google 쪽 변경은 읽기 또는 제한적 import만 허용

### Stage 2

- 특정 calendar만 selective bidirectional sync
- 충돌은 자동 확정 대신 review queue로 보냄

### Stage 3

- 반복 일정, 삭제 전파, 이동, 예외 인스턴스까지 포함한 정식 양방향 sync

## 리팩터링 우선순위

1. simple read path를 canonical command passthrough로 단순화
2. Molly fast CLI가 core command vocabulary를 직접 노출하게 정리
3. structured bridge는 write 중심으로 축소
4. Google sync를 optional adapter로 재도입
5. Gmail ingestion은 candidate pipeline으로 유지

## 이번 단계에서 바라는 상태

- `today/upcoming/week/month` 같은 기본 조회는 바로 Molly core command로 들어간다.
- OpenClaw와 Telegram은 자연어 UX를 담당하되 실행 권한은 갖지 않는다.
- local-first 원칙은 유지하고, Google Calendar는 실용적인 sync layer로 복구한다.
