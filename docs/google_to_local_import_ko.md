# Google To Local Calendar Import

## 목적

복구된 Google Calendar를 Molly의 주 저장소로 다시 쓰려는 것은 아니다.  
이번 단계의 목적은 기존에 Google 쪽에 이미 입력되어 있던 가족 일정을 로컬 캘린더 DB로 안전하게 가져오는 것이다.

즉 Google은 당분간:

- 과거 입력 데이터의 이관 소스
- 필요 시 이메일/외부 입력 창구

정도로만 취급한다.

## 이번 단계에서 추가한 것

- `calendar_import.py`
- `scripts/import_google_calendar_to_local.py`

이 경로는:

1. Google Calendar OAuth로 읽기 연결
2. Molly의 로컬 calendar DB 연결
3. 각 가족 캘린더 이벤트 조회
4. 로컬 DB에 안전하게 삽입

순서로 동작한다.

## 안전장치

### 1. 재실행 가능한 import

Google 이벤트 ID를 로컬 이벤트 레코드에 함께 저장한다.

- `source_backend`
- `source_event_id`

이를 기반으로 동일한 Google 이벤트를 다시 import하려고 하면 중복 삽입하지 않고 skip 한다.

즉 한 번 가져온 뒤 다시 실행해도 비교적 안전하다.

### 2. 보수적 recurrence 지원

지금은 로컬 backend가 안정적으로 처리할 수 있는 recurrence만 import 한다.

현재 지원:

- 단일 `RRULE`
- `FREQ=WEEKLY`
- `BYDAY=...` 포함

현재 skip:

- 더 복잡한 recurrence
- 예외일(`EXDATE`)이 포함된 recurrence
- 로컬 backend가 정확히 재현하기 어려운 형태

이 단계에서는 “적게 가져오더라도 틀리지 않게”가 우선이다.

## 실행 방법

먼저 dry-run:

```bash
./.venv/bin/python scripts/import_google_calendar_to_local.py --dry-run
```

실제 import:

```bash
./.venv/bin/python scripts/import_google_calendar_to_local.py
```

기간을 직접 지정할 수도 있다.

```bash
./.venv/bin/python scripts/import_google_calendar_to_local.py --start 2025-01-01 --end 2027-12-31
```

기본 범위는:

- 시작: 오늘 기준 180일 전
- 종료: 오늘 기준 365일 후

## 현재 판단

이 import 경로는 Google을 다시 주 backend로 되돌리기 위한 작업이 아니다.  
로컬 중심 구조를 유지하면서, 이미 입력된 일정을 잃지 않고 옮기기 위한 현실적인 보조 경로다.
