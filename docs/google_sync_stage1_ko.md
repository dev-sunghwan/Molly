# Google Calendar Sync Stage 1

## 목표

Google Calendar를 Molly의 주 저장소로 되돌리지 않고, 로컬 캘린더를 기준으로 Google Calendar를 보조 미러처럼 다시 붙인다.

이번 단계의 원칙은 단순하다.

- source of truth는 local calendar다.
- Google Calendar는 optional sync target이다.
- Stage 1에서는 Google에 없는 일정만 추가한다.
- Google의 기존 이벤트를 수정하거나 삭제하지 않는다.

## 왜 이렇게 가는가

완전 양방향 sync는 금방 복잡해진다.

- 충돌 해결
- 반복 일정 예외 처리
- 삭제 전파
- 사용자가 어느 쪽에서 바꿨는지 판별

지금은 그 복잡도를 피하고, 실용적인 가치를 먼저 얻는 것이 맞다.

- 휴대폰/웹에서 Google Calendar로 일정 확인 가능
- Molly local 데이터의 외부 미러 확보
- 필요 시 가족 공유 surface로 활용 가능

## Stage 1 동작 방식

입력 경로:

`local calendar -> sync scan -> Google duplicate check -> insert missing events only`

판단 기준:
- calendar
- title
- start/end date
- start/end time
- recurrence

위 기준이 같으면 이미 있는 일정으로 보고 skip 한다.

## 범위

지원:
- 단일 이벤트
- all-day 이벤트
- 단순 weekly recurrence 1개 RRULE

보수적으로 skip:
- 더 복잡한 recurrence
- 수정 전파
- 삭제 전파
- conflict auto-resolution

## 실행 방법

우선 dry-run:

```bash
./.venv/bin/python scripts/sync_local_to_google_calendar.py
```

특정 캘린더만 dry-run:

```bash
./.venv/bin/python scripts/sync_local_to_google_calendar.py --calendar family --calendar younha
```

실제 반영:

```bash
./.venv/bin/python scripts/sync_local_to_google_calendar.py --apply
```

기간 지정:

```bash
./.venv/bin/python scripts/sync_local_to_google_calendar.py --start 2026-01-01 --end 2026-12-31 --apply
```

## 운영 권장

- 처음에는 dry-run으로 detail을 확인한다.
- 그다음 특정 calendar만 `--apply` 한다.
- 마지막에 전체 calendar로 넓힌다.

## 다음 단계 후보

Stage 2에서는 아래 중 하나를 고를 수 있다.

1. Google 변경을 review queue로 가져오는 selective import
2. local event와 Google event의 mapping 저장
3. 제한된 update propagation

하지만 지금은 Stage 1의 보수적 미러링이 가장 맞다.
