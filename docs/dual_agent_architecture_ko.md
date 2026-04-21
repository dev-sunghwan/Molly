# Dual-Agent Architecture

## 1. 목적

Molly를 하나의 agent로 계속 운영하면 실사용 텔레그램 응답과 개발/운영 보조 문맥이 서로 섞이게 된다.
이 문서는 Molly를 다음 두 agent로 분리하는 방향을 정리한다.

- Telegram Fast Agent
- Slack Dev Agent

핵심 목표는 다음과 같다.

- Telegram 실사용 응답 속도 개선
- 일정 처리 문맥과 개발 문맥 분리
- OpenClaw 컨텍스트 부하 감소
- 고성능 모델이 필요한 개발/운영 보조 채널 확보

## 2. 권장 구조

권장 구조는 아래와 같다.

`Telegram Molly Bot -> Telegram Fast Agent -> Molly Core -> Local Calendar DB`

`Slack Dev Bot -> Slack Dev Agent -> Molly Core / Logs / Docs / Dev Tools`

두 agent는 공통으로 Molly Core를 사용할 수 있지만, 역할과 권한 범위는 분리한다.

## 3. Telegram Fast Agent

### 3.1 목적

- 가족 구성원이 실제로 쓰는 일정 assistant
- 빠른 응답과 짧은 clarification
- 일정 생성/조회/수정/삭제 중심

### 3.2 모델 방향

- 더 가벼운 모델 사용
- 낮은 reasoning 비용
- 짧은 context 유지

### 3.3 동작 원칙

- scheduling request면 바로 Molly fast CLI를 우선 사용
- memory/file 탐색은 기본적으로 피함
- 정보가 충분하면 즉시 실행
- 부족하면 짧게 한 가지씩 되묻기
- 실제 일정 반영은 deterministic Python이 수행

### 3.4 권장 문맥 구성

- 짧은 `SOUL.md`
- 짧은 `AGENTS.md`
- 최소 household memory
- 일정 처리 규칙, 가족 캘린더 매핑, recurrence 매핑만 유지

## 4. Slack Dev Agent

### 4.1 목적

- 개발 보조
- 운영 상태 점검
- 로그 분석
- 설계 논의
- 문제 재현 및 디버깅

### 4.2 모델 방향

- 더 강한 모델 사용
- 긴 설명과 더 깊은 reasoning 허용
- 비교적 큰 context 허용

### 4.3 동작 원칙

- 실사용 사용자 응답 속도보다 개발 생산성을 우선
- 문서, 로그, 테스트 결과를 길게 설명해도 됨
- 필요 시 Molly Core를 호출할 수 있지만 기본 역할은 개발/운영 보조
- 운영 캘린더에 대한 파괴적 작업은 명시적 요청 없이 수행하지 않음

## 5. 왜 분리가 필요한가

현재 Telegram 쪽에서 체감되는 지연은 Molly Core 실행보다 OpenClaw 문맥 및 추론 비용의 영향이 더 크다.
따라서 다음 분리가 의미가 있다.

- 실사용 scheduling path는 작고 빠르게 유지
- 개발/설계/디버깅 path는 별도 agent로 분리

이 분리는 속도뿐 아니라 다음 문제도 줄인다.

- 개발 대화가 실사용 assistant 문맥을 오염시키는 문제
- 텔레그램에서 과도하게 긴 설명이 나오는 문제
- 불필요한 tool/schema/context 적재

## 6. 권장 권한 경계

Telegram Fast Agent:

- 허용: Molly scheduling CLI, 최소 runtime execution
- 제한: 광범위한 파일 탐색, 긴 문서 읽기, 메모리 탐색, 개발용 툴 사용

Slack Dev Agent:

- 허용: 문서 조회, 로그 분석, 테스트 실행, 필요 시 Molly CLI
- 제한: 명시적 요청 없는 운영 일정 파괴 작업

## 7. 구현 전략

### Phase A. 문맥 분리

- Telegram Fast Agent용 workspace 문맥 최소화
- Slack Dev Agent용 workspace 또는 별도 prompt profile 정의

### Phase B. 모델 분리

- Telegram 연결 agent는 경량 모델로 설정
- Slack 연결 agent는 고성능 모델로 설정

### Phase C. 채널 분리

- Telegram bot은 실사용 채널
- Slack bot은 개발/운영 채널

### Phase D. 운영 검증

- Telegram 일정 조회/생성 latency 확인
- Slack 개발 agent에서 로그/설계 품질 확인

## 8. Molly Core와의 경계

두 agent 모두 Molly Core를 사용할 수 있지만, 아래 원칙은 유지한다.

- 날짜/시간 정규화는 Python
- 캘린더 키 검증은 Python
- 중복 방지는 Python
- recurrence 생성은 Python
- create/update/delete/search 실행은 Python

Agent는 아래만 맡는다.

- 자연어 해석
- clarification 문안 생성
- 이메일 요약
- schedule candidate 추출

## 9. 우선순위 제안

권장 순서는 다음과 같다.

1. Telegram Fast Agent와 Slack Dev Agent 역할 문서화
2. Telegram 쪽 경량 모델 및 최소 context 구성
3. Slack bot/agent 추가
4. 실제 Telegram latency 재검증
5. Gmail intake 기능을 이 구조 위에 추가

## 10. 결론

Dual-agent는 단순한 구조 과시가 아니라 Molly의 현재 문제와 잘 맞는 실용적 분리다.

- Telegram은 빠르고 좁게
- Slack은 깊고 넓게
- 실행은 계속 Molly Core가 담당

이 방향은 full rewrite 없이 현재 구조를 확장하는 가장 현실적인 경로다.
