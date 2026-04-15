# Molly Local-First 전환 기록 (국문)

## 1. 배경

Molly는 처음에 Molly 전용 Gmail 계정과 Google Calendar를 system of record로 사용하는 방향으로 설계되었다.

이 구조는 빠르게 시작하기에는 실용적이었지만, 2026-04-15에 Molly 전용 Google 계정이 정책 위반 의심으로 비활성화되면서 운영 리스크가 명확해졌다.

이 사건은 다음 사실을 보여줬다.

- Molly의 핵심 가치는 Google 계정이 아니라 가족 일정 관리 assistant 자체에 있다.
- 외부 계정 정책과 플랫폼 검토 상태가 시스템 전체의 가용성을 좌우하면 장기 운영 리스크가 크다.
- Telegram, deterministic Python logic, clarification flow, state storage 같은 핵심 자산은 Google 없이도 유지 가능하다.

이 기록은 왜 Molly가 Google 중심 구조에서 local-first 구조를 진지하게 검토하게 되었는지 남기기 위한 것이다.

## 2. 방향 전환의 목표

새 목표는 다음과 같다.

- Molly의 source of truth를 로컬 저장소로 옮긴다.
- Telegram을 주 인터페이스로 유지한다.
- OpenClaw/LLM은 해석 계층에만 사용한다.
- Google Calendar와 Gmail은 필수 백엔드가 아니라 optional adapter로 낮춘다.
- Gmail 계정 복구 여부와 무관하게 Molly 개발과 실사용이 계속 가능해야 한다.

한 줄로 요약하면:

`Telegram -> OpenClaw/LLM -> Molly Core -> Local Calendar Store`

## 3. 무엇을 유지하고 무엇을 바꾸는가

유지할 것:

- Telegram bot 인터페이스
- intent schema
- clarification flow
- SQLite state storage
- deterministic Python validation / execution 원칙
- scheduler / reminder 구조
- OpenClaw integration 방향

교체하거나 축소할 것:

- Google Calendar를 기본 execution backend로 보는 관점
- Gmail을 기본 ingestion 채널로 보는 관점
- Google OAuth / token 중심 운영 방식

즉, full rewrite가 아니라 backend 중심 migration에 가깝다.

## 4. 권장 목표 구조

### 4.1 Core

- `ScheduleIntent`
- validation / normalization
- clarification
- execution policy

### 4.2 Local Calendar Store

- SQLite 기반 캘린더 / 이벤트 / 리마인더 저장
- 가족 구성원별 calendar 개념 유지
- audit / replay protection 유지

### 4.3 Interfaces

- Telegram: 주 입력과 응답 채널
- Email: 추후 별도 adapter
- Optional sync adapters: Google, ICS, CalDAV 등

### 4.4 Adapters

- OpenClaw adapter: 자연어 해석
- Google adapter: 나중에 복구되면 선택적 sync 또는 import/export
- Email adapter: Gmail 고정이 아니라 provider-agnostic 방향 검토

## 5. 왜 local-first가 맞는가

### 5.1 장점

- 외부 계정 정지에 덜 의존적이다.
- source of truth가 프로젝트 내부에 남는다.
- 테스트와 로컬 개발이 단순해진다.
- 원하는 안전 규칙과 감사 로그를 직접 설계할 수 있다.
- 장기적으로 특정 벤더 종속을 줄일 수 있다.

### 5.2 단점

- Google Calendar 같은 완성된 외부 UI가 기본 제공되지 않는다.
- 외부 일정 공유와 초대장 처리 기능은 직접 더 설계해야 한다.
- 이메일 ingestion은 Gmail 외 대체 수단을 따로 정해야 한다.

## 6. migration plan 초안

### Step 1. Google 데이터 백업

- Molly Gmail 계정의 가능한 데이터 백업
- 기존 Google Calendar 이벤트 export 확보
- 기존 캘린더 구조와 calendar ids 기록

### Step 2. Local calendar schema 도입

- `calendars`
- `events`
- `event_recurrence`
- `reminders`
- `event_log`

### Step 3. Execution backend 분리

- 현재 Google Calendar write 로직과 Molly core intent execution 경계 분리
- 로컬 SQLite backend를 새로운 기본 실행 대상으로 도입

### Step 4. Telegram 실사용 우선

- Telegram 자연어 -> local backend create/update/delete
- 조회 / 리마인더 / daily summary를 local backend 기준으로 전환

### Step 5. Import / Sync layer

- Google export import
- optional Google sync
- optional ICS export

### Step 6. Email 재설계

- Gmail 고정이 아니라 provider-agnostic 이메일 ingestion 검토
- 필요 시 IMAP, forwarding, webhook 기반 수신 경로 검토

## 7. 운영 원칙

- Google 복구 여부와 무관하게 Molly core는 독립적으로 작동해야 한다.
- Google은 다시 붙더라도 optional adapter여야 한다.
- deterministic Python execution과 auditability는 유지한다.
- 사용성 개선의 우선순위는 계속 Telegram이다.

## 8. 다음 설계 작업

다음으로 구체화할 항목:

- local calendar schema 초안
- Google backend와 local backend의 공통 repository interface
- event import 계획
- Telegram 실사용 기준 기능 우선순위 재정렬

실제 MVP 범위와 입력 채널 우선순위는 [local_first_mvp_ko.md](/home/sunghwan/projects/Molly/docs/local_first_mvp_ko.md:1)에 별도 정리한다.
