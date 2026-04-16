# Local Repository Cleanup

## 배경

로컬 SQLite 백엔드가 이미 기본 동작 경로가 되었지만, 런타임 경계는 여전히 `calendar_client`와 `gcal_service`라는 Google 중심 흔적을 갖고 있었습니다. 이 상태는 실제 실행은 local-first인데도, 코드 읽기와 다음 단계 확장에서 혼동을 만들 수 있었습니다.

## 이번 단계에서 정리한 내용

- `calendar_repository.py`를 추가해 Molly의 공용 캘린더 실행 경계를 만들었습니다.
- Google 구현은 `google_calendar_backend.py`로 분리했습니다.
- `bot.py`, `scheduler.py`는 더 이상 `gcal_service`에 직접 의존하지 않고 `CalendarRepository`를 사용합니다.
- 기존 `calendar_client.py`는 바로 제거하지 않고, 호환성 유지를 위한 얇은 shim으로 축소했습니다.

## 의미

이 정리는 기능 추가 단계라기보다, 이후 OpenClaw 연동과 추가 입력 채널 확장을 더 안전하게 만들기 위한 구조 정리 단계입니다. 특히 Telegram 자연어 처리 결과가 어떤 백엔드로 실행되든 동일한 저장소 경계를 지나가도록 정리했다는 점이 중요합니다.

## 남아 있는 제한

- local backend의 recurring event 단일 occurrence 수정/삭제 제한은 그대로입니다.
- 일부 과거 문서에는 아직 `calendar_client.py`가 주 실행 모듈처럼 설명되어 있습니다.

## 다음 단계

다음 단계는 실제 `OpenClaw Telegram provider`를 연결해서, Telegram 메시지에 대해 구조화 draft를 먼저 시도하고 실패 시 휴리스틱으로 돌아가도록 만드는 것입니다.
