# Google Update/Delete Sync 계획

## 현재 상태

- Local SQLite calendar DB가 source of truth다.
- Google Calendar는 비동기 sync target이다.
- `google_sync_outbox`는 create/update/delete/move/delete-series 작업을 기록할 수 있다.
- production worker는 현재 `create`만 Google에 반영한다.
- `update`, `delete`, `move`, `delete_series`는 아직 Google에 반영하지 않고 `unsupported`로 처리한다.

## 왜 바로 켜지 않는가

Google update/delete는 create보다 위험하다.

- 잘못 매칭하면 실제 가족 일정을 삭제할 수 있다.
- recurring event의 series/occurrence 구분이 필요하다.
- local event id와 Google event id mapping이 없으면 제목/시간 기반 추정 삭제가 필요해진다.
- Google에 이미 수동 수정된 이벤트가 있을 수 있다.

따라서 update/delete sync는 local event id와 Google event id mapping이 있는 row부터 제한적으로 시작한다.

## 목표

1. Local mutation 결과가 어떤 local event row를 바꿨는지 명확히 알 수 있게 한다.
2. Outbox row가 `local_event_id`와 operation-specific payload를 가진다.
3. `google_event_mappings`에서 Google event id를 찾을 수 있는 경우에만 update/delete를 실행한다.
4. mapping이 없으면 Google Calendar를 추정 수정/삭제하지 않고 `needs_mapping` 또는 `unsupported`로 남긴다.
5. 모든 update/delete worker 동작은 dry-run으로 먼저 검증한다.

## Stage A. Mutation Result Contract

현재 Molly Core는 사용자-facing message를 기준으로 성공 여부를 판단하는 부분이 있다. update/delete/move를 안전하게 sync하려면 repository/backend가 mutation result를 구조적으로 반환해야 한다.

Status:

- 2026-05-10 완료.
- local backend에 `LocalMutationResult`와 `*_result` mutation helper를 추가했다.
- 기존 string-returning public methods는 유지한다.
- `CalendarRepository`가 result helper를 노출한다.
- `MollyCore`가 update/delete/move/delete_series outbox row에 `local_event_id`와 `mutation_result` payload를 넣는다.
- Google worker는 아직 update/delete를 실행하지 않고 기존처럼 unsupported로 둔다.

필요 필드:

- `success`
- `operation`
- `local_event_id`
- `target_calendar`
- `previous_calendar`
- `title`
- `target_date`
- `start_time`
- `end_time`
- `recurrence`

위 구조는 user message와 별개로 outbox payload를 만들 때 사용한다.

## Stage B. Delete Sync

가장 먼저 지원할 mutation은 non-recurring single event delete다.

조건:

- outbox operation = `delete`
- `local_event_id` 존재
- `google_event_mappings.local_event_id` 또는 idempotency key로 Google event id 확인 가능
- recurrence 없음

동작:

1. mapping 조회
2. Google event id가 없으면 `needs_mapping`
3. Google event id가 있으면 Google Calendar `events.delete`
4. 성공하면 outbox `done`
5. Google에서 이미 삭제되어 404가 나면 idempotent success로 `done`

금지:

- title/date/time만으로 Google event를 찾아 삭제하지 않는다.
- mapping 없는 delete는 자동 처리하지 않는다.

## Stage C. Update Sync

delete가 안정화된 뒤 update를 지원한다.

조건:

- outbox operation = `update`
- `local_event_id` 존재
- mapping으로 Google event id 확인 가능
- non-recurring single event 우선

동작:

1. mapping 조회
2. Google event id가 없으면 `needs_mapping`
3. Google event get
4. 허용 필드만 patch
   - summary
   - start
   - end
   - recurrence 없는 단일 이벤트
5. 성공하면 outbox `done`

## Stage D. Move Sync

Google Calendar에는 cross-calendar move가 단순 patch가 아닐 수 있다. 안전한 방식은 copy/create + delete다.

초기 정책:

- move는 계속 `unsupported`
- 실사용 필요가 확인되면 별도 설계

## Stage E. Recurring Events

Recurring update/delete는 series와 occurrence 구분이 필요하다.

초기 정책:

- recurring series create만 현재 수준 유지
- recurring update/delete는 계속 `unsupported`
- single occurrence deletion은 local recurring exception 모델이 안정화된 뒤 Google sync를 붙인다.

## 검증 계획

각 단계는 fake Google service 테스트와 live dry-run을 먼저 통과해야 한다.

필수 테스트:

- mapping 있는 delete 성공
- mapping 없는 delete는 Google API 호출 없이 `needs_mapping`
- Google 404 delete는 `done`
- mapping 있는 update patch 성공
- unsupported recurrence는 Google API 호출 없이 `unsupported`
- worker retry/failed 상태 유지

## 운영 원칙

- Telegram 응답은 항상 local DB 성공 기준이다.
- Google sync 실패는 Telegram 응답을 막지 않는다.
- Google update/delete는 mapping 없는 추정 실행을 하지 않는다.
- Slack/admin에서 outbox 상태를 먼저 확인하고 확장한다.
