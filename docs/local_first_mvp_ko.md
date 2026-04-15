# Local-First Molly MVP (국문)

## 1. 제품 정의

Molly는 가족 일정 관리를 대신해주는 local-first family assistant이다.

중요한 것은 외부 캘린더 플랫폼 자체가 아니라 다음 경험이다.

- 가족 구성원이 Telegram 같은 메신저로 Molly에게 자연어로 말을 건다.
- Molly가 그 요청을 이해하고 필요한 정보를 되묻는다.
- Molly가 가족 구성원별 일정을 안전하게 저장하고 조회해준다.
- 외부에서 받은 일정 정보도 Molly에게 쉽게 전달해 일정 후보로 만들 수 있다.
- Molly가 리마인더와 일일 요약을 제공한다.

## 2. Source of Truth

MVP에서 일정의 system of record는 로컬 SQLite calendar store이다.

- 로컬 backend가 기본 저장소다.
- Telegram이 주 인터페이스다.
- OpenClaw/LLM은 해석기 역할만 한다.
- Google Calendar/Gmail은 복구되더라도 optional adapter다.

## 3. MVP에서 꼭 되는 것

### 3.1 Telegram 일정 관리

- 자연어로 일정 조회
- 자연어로 일정 추가
- 일정 수정
- 일정 삭제
- 가족 구성원별 캘린더 선택
- 애매한 경우 clarification

### 3.2 로컬 저장과 실행

- 가족 구성원별 calendar 개념 유지
- 로컬 DB에 일정 저장
- deterministic Python validation
- audit/logging 유지
- reminder / daily summary 유지

### 3.3 외부 정보 입력

초기에는 자동 이메일 연동보다 아래 경로를 우선한다.

- 이메일 본문을 Telegram에 forward / copy-paste
- 학교/학원/클럽 공지 텍스트를 Telegram에 붙여넣기
- 나중에 이미지/PDF까지 확장 가능

즉, 외부 정보 ingestion의 초기 MVP는:

`외부 공지 텍스트 -> Telegram -> Molly 해석 -> 일정 후보 -> 확인 -> 저장`

## 4. MVP에서 일부러 하지 않는 것

- 범용 캘린더 플랫폼 재구현
- 고급 공유 권한 시스템
- 완전한 초대장/캘린더 표준 구현
- 모든 반복 일정 예외 처리
- Gmail 의존 자동화부터 시작하는 설계
- 여러 온라인 서비스 동시 연동

## 5. 입력 채널 우선순위

### 1순위

- Telegram 자연어

예:

- `내일 오후 5시에 윤하 테니스 넣어줘`
- `다음주 하늘 학교 행사 보여줘`

### 2순위

- 외부 공지 텍스트를 Telegram에 전달

예:

- 학교/학원 메일 본문 복붙
- 클럽 공지 내용을 그대로 전달

### 3순위

- 이미지 / PDF / 스크린샷

이건 나중 단계다.

### 4순위

- 자동 이메일 intake
- IMAP / forwarding / webhook / Gmail adapter

이건 편의 기능이며 core가 아니다.

## 6. 제품 원칙

- Molly의 본질은 가족 비서 경험이다.
- 외부 서비스는 필수 기반이 아니라 선택적 adapter다.
- LLM은 이해와 초안 생성에만 쓰고 실행은 Python이 한다.
- 애매하면 Molly가 되묻는다.
- 실사용성 우선순위는 Telegram이다.

## 7. 다음 3개 phase

### Phase A. Local Repository Cleanup

- local/google backend 공통 interface 정리
- scheduler/bot의 backend 의존성 정리

### Phase B. Telegram Assistant UX

- Telegram 자연어 범위 확장
- OpenClaw provider 실제 연결
- clarification 품질 개선

### Phase C. External Notice Intake

- Telegram에 전달된 공지 텍스트를 일정 후보로 변환
- 필요 시 사람/날짜/시간 clarification
- 후보 저장과 실행 흐름 정리

## 8. 성공 기준

MVP 성공 기준은 단순하다.

- 가족이 Telegram으로 Molly에게 일정 관리를 실제로 맡길 수 있다.
- 외부 공지 내용을 Molly에게 전달해서 일정으로 바꾸는 것이 충분히 편하다.
- Google 계정 상태와 무관하게 Molly가 계속 동작한다.
