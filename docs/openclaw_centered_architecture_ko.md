# OpenClaw-Centered Molly Architecture

## 1. 왜 이 방향으로 정리했는가

Molly 프로젝트의 핵심은 특정 Telegram bot 구현이 아니라, 아래 두 가지를 안정적으로 결합하는 데 있다.

- 자연어 대화와 모호성 해소
- 일정 관리의 안전한 실행

이 요구를 기준으로 보면 Telegram bot 자체는 UI 채널일 뿐이다.

즉 중요한 것은:

- 어떤 bot을 쓰는가
- 어떤 계정으로 메시지를 받는가

보다도,

- 누가 자연어를 이해하는가
- 누가 최종 일정을 생성/수정/삭제하는가

이다.

이 관점에서 Molly의 역할을 다시 나누면:

- OpenClaw: 대화형 해석기, clarification 담당
- Molly Core: deterministic execution engine
- Local calendar DB: system of record

가 된다.

## 2. 최종 지향 구조

권장 구조는 아래와 같다.

`User -> OpenClaw-connected Telegram bot -> OpenClaw -> Molly Core -> Local calendar DB`

여기서 OpenClaw는 사용자와 직접 대화한다.

- 자연어 의미 파악
- 필요한 정보가 없을 때 되묻기
- 애매한 날짜/시간/대상 캘린더 정리
- 구조화된 실행 요청 생성

그리고 Molly Core는 구조화된 요청만 받아 실행한다.

- 요청 스키마 검증
- 날짜/시간 정규화
- 충돌 검사
- 일정 생성/수정/삭제
- 로그 기록

## 3. 역할 분리

### 3.1 OpenClaw가 맡는 일

- Telegram UI와의 대화
- 자연어 해석
- 누락 정보 수집
- clarification 질문
- 사용자 의도를 구조화된 draft/request로 변환
- 실행 결과를 사람이 읽기 쉬운 말로 다시 전달

### 3.2 Molly Core가 맡는 일

- create/view/update/delete/search 같은 캘린더 작업 실행
- 로컬 DB 읽기/쓰기
- validation / normalization
- recurring rule 처리
- reminder / summary용 데이터 제공
- audit/logging 유지

## 4. 중요한 원칙

이 구조에서 LLM은 실행기가 아니다.

LLM은:

- 해석한다
- 묻는다
- 정리한다

하지만 직접 일정 DB를 수정하지 않는다.

실제 쓰기 작업은 항상 Molly Core가 담당한다.

즉 다음 경계는 유지해야 한다.

- OpenClaw: interpretation boundary
- Molly Core: execution boundary

이 경계가 있어야 다음 문제가 줄어든다.

- LLM 오해로 인한 잘못된 일정 추가
- 애매한 날짜 표현의 무리한 실행
- 대상 캘린더 추론 오류
- 충돌 확인 없이 일정이 반영되는 문제

## 5. 왜 기존 Molly Telegram bot 중심 구조보다 이 방향이 더 맞는가

기존 구조에서는 Molly bot이 직접 입력을 받고, 내부에서 heuristic 또는 provider를 붙이는 식이었다.

이 방식도 동작은 가능하지만, 장기적으로는 다음 한계가 있다.

- 대화형 clarification UX가 bot 내부 구현과 강하게 결합됨
- LLM 보강이 들어갈수록 bot 코드가 비대해짐
- “가족 비서처럼 대화한다”는 경험이 Molly bot과 NLU adapter 사이에 나뉘게 됨

반대로 OpenClaw 중심 구조는 다음 장점이 있다.

- 대화형 UX를 OpenClaw가 자연스럽게 담당
- Molly Core는 점점 더 작고 안정적인 실행 엔진으로 정리 가능
- 입력 채널을 Telegram 외로 늘려도 구조가 유지됨
- 외부 공지/요약/후속 질문도 같은 대화 계층에서 처리 가능

## 6. 현재 확인된 현실 제약

이전 시도에서 Molly가 OpenClaw를 `OpenAI-compatible HTTP endpoint`처럼 직접 호출하려 했지만, 현재 로컬 OpenClaw는 그 형태의 inference endpoint를 바로 노출하는 것으로 확인되지 않았다.

확인된 점:

- 로컬 OpenClaw gateway/control UI는 살아 있다.
- 하지만 `/v1/chat/completions` 같은 경로는 현재 확인되지 않았다.
- OpenClaw는 raw HTTP inference server보다는 CLI / gateway / agent runtime 중심 구조에 더 가깝다.

이 의미는:

- OpenClaw를 못 쓴다는 뜻이 아니다.
- Molly가 붙는 방식이 `HTTP direct call`이 아닐 가능성이 높다는 뜻이다.

## 7. Molly와 OpenClaw의 실제 연결 방식 후보

### 후보 A. CLI adapter

OpenClaw의 CLI를 Molly 외부에서 호출 가능한 해석 계층으로 사용한다.

예:

- `openclaw infer model run ...`
- 또는 향후 agent/capability command

장점:

- 현재 확인된 표면과 가장 잘 맞음
- 빠르게 MVP 가능
- 구현 난이도가 낮음

단점:

- 프로세스 호출/출력 파싱 계층이 필요
- 장기적으로는 tool/MCP보다 덜 우아함

### 후보 B. OpenClaw tool / capability integration

Molly Core 기능을 OpenClaw가 tool처럼 직접 부르게 한다.

장점:

- 구조적으로 가장 자연스러움
- OpenClaw 중심 아키텍처와 잘 맞음

단점:

- 초기 구현 난이도가 더 높음
- OpenClaw 측 extension surface 이해가 더 필요함

### 후보 C. Local HTTP bridge

Molly Core를 localhost API로 띄우고 OpenClaw가 호출하게 한다.

장점:

- 시스템 간 경계가 명확함

단점:

- 프로세스 하나가 더 필요함
- 지금 단계에서는 과한 분리일 수 있음

## 8. 현재 권장 구현 순서

가장 실용적인 첫 연결은 다음이다.

### Step 1. Molly Core 실행 인터페이스 정리

예:

- `create_event`
- `view_daily`
- `view_range`
- `update_event`
- `delete_event`

를 구조화된 입력으로 받는 단일 실행 진입점 준비

### Step 2. OpenClaw에서 호출할 첫 adapter 결정

초기에는 CLI adapter를 권장한다.

즉 OpenClaw가 최종적으로 아래와 같은 구조화 요청을 만들게 한다.

```json
{
  "action": "create_event",
  "target_calendar": "younha",
  "title": "Tennis",
  "target_date": "2026-04-16",
  "start_time": "17:00",
  "end_time": "18:00",
  "all_day": false
}
```

그리고 Molly Core는 이 요청만 받아 실행한다.

### Step 3. 첫 end-to-end use case는 create_event 하나만 연결

범위를 좁게 잡는다.

- Telegram 대화
- clarification
- structured request 생성
- Molly Core 실행
- 결과 응답

이 흐름이 안정되면 그다음에 view/update/delete로 확장한다.

## 9. 구현 원칙

- Telegram bot은 교체 가능한 UI다.
- OpenClaw는 assistant/controller다.
- Molly Core는 executor다.
- Local calendar DB는 source of truth다.
- LLM은 interpretation에만 사용한다.
- 실행과 검증은 deterministic Python이 담당한다.

## 10. 현재 결론

설계 방향은 이제 충분히 명확하다.

Molly의 중심은 더 이상 “Telegram bot 내부에 NLU를 넣는 것”이 아니라,

`OpenClaw가 대화를 담당하고 Molly Core가 실행을 담당하는 구조`

로 정리하는 것이 맞다.

다음 구현 phase는 이 구조를 실제로 연결하는 첫 실행 인터페이스를 만드는 것이다.
