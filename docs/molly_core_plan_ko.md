# Molly Core Plan

## 1. 목적

이 문서는 앞으로 Molly Core를 어떤 순서로 강화할지 정리한다.

현재 우선순위는 다음과 같다.

- 일정 입력을 더 유연하게 받는 것보다
- 일정을 더 안전하게 저장, 수정, 삭제, 추적하는 것
- 이메일 후보를 확인 가능한 흐름으로 연결하는 것
- 반복 일정, 복수일 일정, 타임존, 리마인더 같은 현실 문제를 안정적으로 처리하는 것

즉 Molly Core는 "더 똑똑한 assistant"보다 "더 단단한 family scheduling engine"으로 발전해야 한다.

## 2. 설계 원칙

다음 원칙을 유지한다.

- 최종 calendar execution은 deterministic Python이 수행한다.
- OpenClaw/LLM은 자연어 해석, 이메일 요약, 후보 추출, clarification 문안에 한정한다.
- Molly Core는 validation, normalization, duplicate suppression, execution, state tracking, audit 역할을 맡는다.
- ambiguity가 있으면 즉시 저장하지 않고 candidate 또는 clarification 상태로 둔다.
- 일정 변경은 나중에 추적 가능한 metadata를 남긴다.

## 3. 핵심 작업 축

### 3.1 Candidate Intake

입력은 바로 실행하지 않고 candidate로 받을 수 있어야 한다.

현재 가장 중요한 intake는 다음 두 가지다.

- Telegram 자연어
- Gmail allowlist 메일

권장 흐름:

`input -> candidate -> validation -> confirmation/clarification -> execution`

### 3.2 Execution Safety

Molly Core는 다음을 계속 책임진다.

- calendar key validation
- date/time normalization
- recurrence normalization
- duplicate suppression
- destructive action safety
- source metadata 저장

### 3.3 Traceability

앞으로는 "이 일정이 어디서 왔는가"를 더 잘 알아야 한다.

예:

- Telegram 직접 요청
- Gmail candidate에서 생성
- Google import 출신
- 수동 수정됨
- 반복 시리즈 일부

## 4. 우선순위 로드맵

## Phase A. Gmail Candidate Confirmation

목표:

- allowlist 메일만 candidate로 분석
- Telegram에서 확인 후 실행

구현 항목:

- candidate 상태 저장
- Telegram 확인 메시지 포맷
- `추가 / 무시 / clarification` 흐름
- confirm 시 Molly Core execution

기대 효과:

- 이메일을 자동으로 곧바로 넣지 않아도 됨
- Gmail은 안전한 inbox intake 채널이 됨

## Phase B. Source Metadata And Execution History

목표:

- 이벤트 출처와 변경 이력을 더 잘 추적

구현 항목:

- source type 저장
- external message id / thread id 저장
- created_by / confirmed_by / updated_by 추적
- execution log 정리

기대 효과:

- 왜 생긴 일정인지 나중에 설명 가능
- Gmail 후보와 기존 일정 충돌 분석이 쉬워짐

## Phase C. Edit/Delete Stabilization

목표:

- 실사용에서 수정/삭제를 덜 위험하게 만들기

구현 항목:

- 같은 제목 일정 다건 처리
- 반복 일정 일부 vs 전체 수정/삭제
- multi-day event 수정 규칙
- ambiguous delete 시 clarification

기대 효과:

- 실사용에서 가장 불편한 구간을 줄임

## Phase D. Timezone-Aware Events

목표:

- 여행, 출장, 해외 일정에서 타임존 혼선을 줄이기

핵심 원칙:

- 이벤트는 가능하면 원래 발생하는 현지 타임존을 함께 저장한다.
- 사용자는 자신의 현재 viewing timezone 기준으로 일정을 볼 수 있어야 한다.
- 리마인더 계산은 event timezone을 기준으로 하되, 표시 문구는 사용자 기준 시간으로 변환 가능해야 한다.

구현 항목:

- event-level `timezone` 필드 추가
- create/update에서 timezone 지정 가능
- 기존 이벤트는 기본 timezone으로 간주
- display 포맷에 event timezone 차이 반영
- reminder 계산에서 timezone-aware datetime 사용

예:

- 런던 병원 일정 -> `Europe/London`
- 한국 여행 중 일정 -> `Asia/Seoul`

## Phase E. Recurrence Refinement

목표:

- weekly recurrence 이후의 현실 문제를 다루기

구현 항목:

- 시리즈 전체 삭제
- 단일 occurrence 수정/삭제
- 단건 일정과 시리즈 충돌 처리
- recurrence duplicate suppression 강화

## Phase F. Reminder Policy Refinement

목표:

- 가족 운영 관점에서 reminder를 더 유용하게 만들기

구현 항목:

- all-day / timed / multi-day reminder 규칙 분리
- event timezone을 고려한 reminder
- 가족 구성원 간 cross-notify 규칙
- duplicate reminder suppression 강화

## 5. 배우자 입력 알림 정책

추가 요구사항:

- JeeYoung가 일정을 입력하면 SungHwan에게도 즉시 알림
- SungHwan이 일정을 입력하면 JeeYoung에게도 즉시 알림

이 요구는 단순한 calendar subscription과는 다르다.

- 이는 "상대방 캘린더를 같이 본다"는 뜻이 아니라
- "상대방이 Molly를 통해 어떤 일정을 추가/수정/삭제했는지 운영 알림을 받는다"는 뜻이다.

따라서 구현은 reminder subscription이 아니라 별도 event-notification 흐름으로 가야 한다.

권장 정책:

- Molly를 통해 일정이 실제로 생성되면 actor를 기록한다
- actor가 `SungHwan`이면 `JeeYoung`에게 notification을 보낸다
- actor가 `JeeYoung`이면 `SungHwan`에게 notification을 보낸다
- 이 알림은 reminder/daily summary와 분리된 별도 메시지다

예:

- `성환이 [윤하] Alpha-Math 일정을 Fri 17-04 17:00–18:00로 추가했어요.`
- `지영이 [Family] Costco 일정을 Sat 18-04 All day로 추가했어요.`

중장기적으로는 아래 정책도 고려 가능하다.

- create/update/delete 별로 알림 종류 분리
- 일정 종류별 spouse notify on/off
- 아이들 관련 일정만 항상 양쪽 notify
- summary/reminder와 spouse-input notification을 완전히 별도 설정으로 운영

## 6. 현재 시점의 가장 추천 순서

가장 실용적인 순서는 다음과 같다.

1. spouse input notification 설계 및 actor/source metadata 정리
2. Gmail candidate confirmation flow
3. source metadata / execution history 강화
4. edit/delete stabilization
5. timezone-aware event support
6. recurrence refinement
7. reminder policy refinement

## 7. 결론

Molly Core의 다음 단계는 "입력 이해"보다 "운영 안정성"이다.

핵심은 다음 네 줄로 요약된다.

- candidate first
- deterministic execution
- source traceability
- timezone and reminder realism
