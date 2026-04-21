# Gmail Intake Allowlist Plan

## 1. 목적

`molly.kim.agent@gmail.com` 으로 들어오는 메일 중 일부를 일정 후보로 분석해 Molly 캘린더에 반영할 수 있도록 한다.
다만 초기 단계에서는 자동화를 넓게 열지 않고, 발신자와 처리 흐름을 좁게 제한한다.

## 2. 초기 범위

초기 분석 대상 메일은 다음 발신자로 한정한다.

- 성환 본인 이메일
- `jylim3287@gmail.com`

그 외 메일은 기본적으로 자동 일정 후보 분석 대상에서 제외한다.

이 제한은 다음 목적을 가진다.

- 노이즈 감소
- 잘못된 일정 생성 위험 감소
- Gmail automation 안정화
- 테스트 범위 축소

## 3. 권장 처리 흐름

권장 흐름은 다음과 같다.

`Gmail Inbox -> Sender Allowlist Filter -> Email Extraction -> Schedule Candidate -> Molly Confirmation -> Local Calendar Write`

즉 초기에는 다음 원칙을 유지한다.

- 무조건 자동 생성하지 않음
- 후보를 먼저 만든 뒤 확인
- 최종 저장은 Molly Core의 deterministic Python이 수행

## 4. 처리 단계

### 4.1 수집

- Gmail API로 inbox 최근 메일 조회
- message id, thread id, subject, from, date, body 추출

### 4.2 필터링

- 발신자 이메일 주소 파싱
- allowlist에 포함된 주소만 분석 대상으로 통과
- 나머지는 `ignored_not_allowlisted` 등 상태로 기록

### 4.3 추출

LLM/OpenClaw는 아래 역할만 맡는다.

- 메일 요약
- 일정 관련 여부 1차 판정
- 제목, 날짜, 시간, 사람, 장소 후보 추출
- 애매성 표시

### 4.4 검증

Python deterministic logic가 아래를 검증한다.

- 대상 가족 구성원 식별
- 날짜/시간 정규화
- 필수 정보 존재 여부
- 중복 여부
- recurrence 여부

### 4.5 확인

초기에는 Telegram으로 아래와 같이 확인하는 흐름을 권장한다.

- 메일 제목 요약
- 추출한 일정 후보
- 대상 캘린더
- 확인 요청

예:

`AWS Summit London 2026 메일에서 [성환] 2026-04-20 15:00~16:00 일정 후보를 찾았어요. 추가할까요?`

### 4.6 실행

- 확인 후 `molly_schedule_action.py create` 또는 동등한 Molly Core 경로 실행
- 저장 결과와 source metadata 기록

## 5. 왜 confirmation-first가 맞는가

이메일은 자연어보다 더 애매한 경우가 많다.
특히 초기에는 다음 문제를 방지해야 한다.

- 광고/안내 메일을 일정으로 오판
- 복수 후보 시간 중 잘못 선택
- 대상 캘린더 잘못 선택
- 이미 있는 이벤트 중복 생성

따라서 초기 정책은 다음이 적절하다.

- allowlist sender
- candidate only
- Telegram confirmation
- deterministic execution

## 6. 데이터 및 상태 저장

Gmail intake에는 별도 workflow 상태가 필요하다.

예:

- `new`
- `ignored_not_allowlisted`
- `ignored_not_schedule_related`
- `candidate_ready`
- `needs_clarification`
- `confirmed`
- `executed`
- `skipped_duplicate`

message id 기준 idempotency도 유지한다.

## 7. 구성값 제안

다음 설정을 명시적으로 두는 것이 좋다.

- `GMAIL_INTAKE_ENABLED=true|false`
- `GMAIL_ALLOWED_SENDERS=ray.sunghwan@gmail.com,jylim3287@gmail.com`
- `GMAIL_CONFIRMATION_MODE=telegram`
- `GMAIL_AUTO_CREATE=false`

초기 기본값은 다음이 적절하다.

- enabled: 필요 시만 켬
- auto create: false
- confirmation mode: telegram

## 8. LLM과 Python의 역할 분리

LLM/OpenClaw:

- 메일 본문 요약
- 일정 관련성 1차 판단
- 구조화 후보 생성
- clarification 문안 초안

Python:

- sender allowlist 확인
- date/time normalization
- calendar mapping validation
- duplicate suppression
- state transition
- actual create/update

## 9. 단계별 구현 제안

### Phase A. Allowlist 기반 intake 재정의

- 허용 발신자 목록 설정
- Gmail worker가 비허용 발신자를 무시하도록 수정

### Phase B. Candidate pipeline

- 메일을 바로 생성하지 않고 candidate로 저장
- Telegram 확인 메시지 포맷 정의

### Phase C. Confirmation flow

- Telegram에서 confirm / reject 처리
- confirm 시 Molly Core 실행

### Phase D. 제한적 자동화

- 충분히 안정화되면 일부 메일 유형만 auto-create 검토

## 10. 결론

Gmail 연동은 다시 붙일 수 있다.
다만 이번에는 Google mailbox를 주 backend로 보지 않고, 안전한 intake 채널로만 사용하는 것이 적절하다.

초기 전략은 다음 네 줄로 요약된다.

- sender allowlist
- candidate extraction
- Telegram confirmation
- deterministic calendar execution
