# Molly 로드맵 (국문)

## 1. 목적

Molly는 가족을 위한 전용 스케줄링 assistant이다.

- Molly는 자체 Gmail 계정을 가진다.
- Molly는 해당 계정 아래에 가족 구성원별 Google Calendar를 소유하고 관리한다.
- 가족 구성원은 자신의 개인 이메일이나 개인 캘린더 접근 권한을 Molly에 직접 주지 않는다.
- Molly가 관리하는 캘린더들이 가족 일정의 system of record 역할을 한다.

Molly의 목표는 단순한 명령형 Telegram bot이 아니라, 자연어와 이메일을 이해하고 안전하게 캘린더를 갱신하는 실용적인 가족 assistant로 진화하는 것이다.

## 1.1 현재 우선순위

현재 제품 우선순위는 다음과 같다.

1. Telegram에서의 자연어 일정 관리 경험 개선
2. 로컬 SQLite 기반 캘린더 backend 설계와 전환
3. 실사용 중 필요한 clarification flow 안정화
4. 이메일 기능은 병행 개발하되, Telegram 실사용성보다 앞세우지 않음

즉, 단기 목표는 Molly를 먼저 "Telegram에서 쓰기 쉬운 scheduling assistant"로 만드는 것이다.
또한 Google 계정 리스크를 줄이기 위해 local-first 구조 전환을 병행 검토한다.
현재 MVP 정의는 [local_first_mvp_ko.md](/home/sunghwan/projects/Molly/docs/local_first_mvp_ko.md:1)를 기준으로 한다.

## 2. 현재 상태 요약

현재 코드베이스에서 이미 구현된 것:

- Telegram bot 기반 운영
- 허용된 사용자만 처리하는 접근 제어
- local SQLite calendar backend 기본 실행 경로
- Google Calendar adapter 경로 유지
- SQLite 기반 workflow state 저장
- 일정 조회: `today`, `tomorrow`, `week`, `month`, `next`, `upcoming`
- 일정 조작: `add`, `edit`, `delete`, `delete all`
- 검색 기능
- APScheduler 기반 리마인더, 아침 요약, 내일 미리보기
- 가족 구성원별 캘린더 분리
- 기본 파서/유틸리티 테스트

아직 없는 것:

- 실제 OpenClaw provider 연결
- provider-agnostic 이메일 수집 및 처리
- Telegram에 전달된 외부 공지 텍스트의 일정 후보화
- 애매성 처리와 대화형 clarification
- 실행 이력과 감사 로그 체계
- OpenClaw/Hermes 연계 구조

## 3. 핵심 운영 원칙

다음 원칙을 유지한다.

- 최종 캘린더 조작은 deterministic Python 로직이 수행한다.
- LLM/agent는 해석, 요약, 후보 추출, 애매성 처리에 한정한다.
- LLM이 직접 Google Calendar API를 호출하지 않는다.
- 이메일이나 자유 문장에 대상 캘린더가 명확하지 않으면 Molly가 다시 되묻는다.
- 대상 인물이 명시되면 해당 인물의 Molly-managed calendar를 우선 후보로 본다.
- 애매하거나 파괴적인 작업은 즉시 실행하지 않고 확인 절차를 거친다.
- 전체 시스템은 full rewrite보다 incremental evolution을 우선한다.

## 4. 권장 아키텍처

Molly는 다음 계층으로 확장한다.

### 4.1 Interface Layer

- Telegram 입력
- Gmail 입력
- 나중의 summary/reminder/weather 출력

### 4.2 Understanding Layer

- 자유 문장 해석
- 이메일 요약
- 일정 관련 정보 추출
- 공통 intent 구조 생성

이 계층에서만 OpenClaw 같은 agent/LLM을 사용한다.

Telegram 자연어의 권장 흐름은 다음과 같다.

- Telegram 메시지
- OpenClaw/LLM extraction
- structured Telegram draft
- Python validation / normalization
- clarification decision
- Molly core execution
- Telegram 응답

즉, OpenClaw는 해석기 역할만 맡고 최종 캘린더 실행은 Molly core가 유지한다.

### 4.3 Decision Layer

- 어느 캘린더에 넣을지 결정
- 필수 정보 누락 여부 판단
- 애매성 판정
- 충돌/중복/위험 작업 검토
- 되물어야 하는지 결정

### 4.4 Execution Layer

- Local calendar read/write
- create/update/delete/search 실행
- reminder scheduling 보조

이 계층은 Python deterministic logic이 책임진다.

Google Calendar와 Gmail은 기본 backend가 아니라 optional adapter로 다루는 방향을 기본값으로 한다.

### 4.5 State and Audit Layer

- 이메일 처리 상태
- 질문 대기 상태
- 실행 결과
- idempotency key
- 변경 이력
- phase completion log

## 5. 기술 방향

### 5.1 Deterministic Python으로 남길 것

- 날짜/시간 정규화
- timezone 처리
- 대상 캘린더 선택 규칙
- 필수 필드 검증
- create/update/delete 실행
- recurrence 생성
- 충돌 및 중복 체크
- destructive action safety rules
- 상태 저장과 재처리 방지
- 스케줄러와 리마인더 로직

### 5.2 Agent/LLM에 맡길 것

- 자연어 이해
- 이메일 요약
- 제목/시간/사람/장소 추출
- 일정 관련 여부의 1차 판정
- ambiguity detection
- clarification question 초안 생성
- 아침/저녁 briefing 문장 생성

이메일 처리에는 hybrid 방식을 사용한다.

- 1차 선택: LLM/OpenClaw가 구조화된 extraction draft를 생성
- fallback: deterministic heuristic 추출
- 최종 판정과 실행: Python validation + Molly workflow

## 6. OpenClaw / Hermes 적용 방안

### 6.1 OpenClaw

OpenClaw는 assistant 해석 계층에 연결한다.

- Telegram 자유 문장 -> intent 변환
- 이메일 본문 -> schedule candidate 추출
- 애매한 경우 질문 생성
- 요약 생성

초기에는 필수 의존성이 아니다.
Molly core와 intent schema를 먼저 정리한 뒤 adapter로 연결한다.

### 6.2 Hermes

Hermes는 이벤트 기반 workflow orchestration에 적합하다.

- 새 이메일 수신 처리
- reminder 트리거
- 아침 요약
- 저녁 미리보기
- 주간 요약
- weather-based daily briefing

초기에는 간단한 Python scheduler를 유지하고, workflow가 복잡해지는 시점에 도입한다.

## 6.3 외부 Adapter 원칙

Google은 다시 붙더라도 optional adapter로 다룬다.

- local SQLite backend를 source of truth로 우선한다.
- Google Calendar는 import/export 또는 optional sync 대상으로 본다.
- Gmail은 provider-agnostic 이메일 adapter 논의의 한 후보로 본다.

local-first 전환 배경과 migration 계획은 [local_first_transition_ko.md](/home/sunghwan/projects/Molly/docs/local_first_transition_ko.md:1)에 별도 기록한다.

## 6.4 Gmail 인증 원칙

Gmail 인증은 Calendar 인증과 분리한다.

- `credentials.json`은 동일한 OAuth client를 재사용할 수 있다.
- Calendar는 `token.json`을 사용한다.
- Gmail은 `gmail_token.json`을 사용한다.
- Gmail scope 변경은 Gmail 토큰만 다시 발급하면 되도록 분리한다.

이 방식은 Gmail과 Calendar 권한의 수명주기와 재인증 시점을 분리하기 위한 것이다.

초기 Gmail 인증은 다음 명령으로 수행한다.

```bash
./.venv/bin/python scripts/gmail_auth_check.py
```

최근 inbox 메시지까지 바로 확인하려면:

```bash
./.venv/bin/python scripts/gmail_auth_check.py --list 5
```

## 7. 단계별 구현 계획

### Phase 0. 현재 기반 정리

목표:

- Python 환경과 실행 기준 정리
- 문서화 시작
- 기존 동작 유지 확인

상태:

- 완료

완료 조건:

- 가상환경 구성
- 의존성 설치
- 기본 테스트 통과
- Telegram bot 실행 확인

### Phase 1. Intent Schema 도입

목표:

- 명령형 입력과 자연어 입력을 같은 구조로 수렴시키는 공통 모델 도입

주요 작업:

- `ScheduleIntent` 정의
- `IntentResolution` 정의
- `ExecutionResult` 정의
- 기존 `commands.py` 출력과의 연결 방식 설계

완료 기준:

- 기존 Telegram 명령이 intent 구조로 변환 가능
- 직접 Calendar write 전에 검증 단계를 거치도록 경계가 분리됨

### Phase 2. Clarification Flow

목표:

- 대상 캘린더나 핵심 정보가 빠진 경우 Molly가 되묻게 만들기

주요 작업:

- 누락 필드 감지
- 질문 메시지 생성
- 질문-응답 상태 저장
- 사용자 후속 답변을 pending intent에 합치는 로직

완료 기준:

- `누구 일정인지` 빠진 요청은 즉시 실행되지 않음
- Molly가 후속 질문을 보내고, 답변 후 이어서 실행 가능

### Phase 3. State Storage

목표:

- SQLite 기반 상태 저장 도입

주요 작업:

- pending clarification 저장
- processed email/message 저장
- execution audit 저장
- idempotency key 저장

완료 기준:

- 재시작 후에도 진행 중 상태 복구 가능
- 중복 메시지/이메일 재처리 방지 가능

### Phase 4. Gmail Ingestion

목표:

- Molly Gmail inbox에서 일정 관련 메일을 읽어 처리 시작

주요 작업:

- Gmail adapter 추가
- unread/new email fetch
- 메일 본문 정규화
- 일정 후보 생성
- 처리 상태 마킹

완료 기준:

- 새 이메일을 읽고 schedule candidate를 만들 수 있음
- 같은 메일이 반복 처리되지 않음

### Phase 5. Assistant Workflow

목표:

- 이메일/자연어 -> 해석 -> 검증 -> 질문 -> 실행 -> 보고 흐름 완성

주요 작업:

- candidate -> confirmed event pipeline
- 결과 Telegram 보고
- 실패/애매성 분기 처리

완료 기준:

- Molly가 자연어/이메일 기반으로 안전하게 일정 추가 가능

### Phase 6. OpenClaw Integration

목표:

- 자유 문장과 이메일 이해 품질 향상

주요 작업:

- OpenClaw adapter
- structured extraction contract
- fallback deterministic parser 유지

완료 기준:

- OpenClaw가 intent 초안을 만들고 Python이 검증/실행

### Phase 7. Hermes Integration

목표:

- 이벤트 기반 자동화 확장

주요 작업:

- email event workflow
- reminder workflow
- daily/weekly summary workflow
- weather workflow

완료 기준:

- 반복성 높은 자동화가 workflow 기반으로 안정화

## 8. 우선순위 작업 목록

다음 순서로 진행한다.

1. 국문/영문 계획 문서와 phase log 유지
2. intent schema 설계
3. clarification flow 구현
4. SQLite 상태 저장 도입
5. Gmail adapter 추가
6. email-to-candidate 처리
7. OpenClaw adapter 추가
8. Hermes workflow 추가
9. weather/context briefing 추가

## 9. 기록 규칙

각 phase가 완료될 때마다 `docs/phase_log.md`에 기록한다.

기록 항목:

- 완료 날짜
- phase 이름
- 목표
- 실제 완료 내용
- 남은 리스크
- 다음 phase

기록은 짧고 사실 중심으로 남긴다.
