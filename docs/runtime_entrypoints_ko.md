# Molly Runtime Entrypoints

이 문서는 현재 운영 기준의 Molly 진입점을 정리한다. 새 연동과 운영 스크립트는 아래의 canonical entrypoint를 우선 사용한다.

## Canonical entrypoints

- `scripts/molly_schedule_action.py`
  - OpenClaw Telegram/Slack에서 호출하는 주 실행 CLI.
  - 일정 생성, 조회, 검색, 수정, 삭제, 이동, Gmail 후보 처리를 모두 담당한다.
  - 주요 subcommand: `command`, `create`, `view`, `search`, `update`, `delete`, `move`, `gmail-process`, `gmail-list`, `gmail-confirm`, `gmail-ignore`, `gmail-notify-pending`.

- `scripts/molly_admin.py`
  - 운영 확인과 장애 대응용 CLI.
  - command journal 조회, sync outbox 확인, 저장된 Telegram 응답 재전송을 담당한다.

- `scripts/run_reminder_worker.py`
  - 일정 reminder와 summary를 보내는 장기 실행 worker.
  - production에서는 legacy `bot.py`가 아니라 이 worker가 reminder를 담당한다.

- `scripts/run_google_sync_worker.py`
  - local-first calendar 변경사항을 Google Calendar로 동기화하는 worker.

## Compatibility entrypoints

아래 파일들은 기존 명령과 테스트를 깨지 않기 위해 남아 있지만, 새 사용처를 만들지 않는다.

- `scripts/molly_create_event.py`
  - `scripts/molly_schedule_action.py create`로 위임하는 create-only 호환 wrapper.

- `scripts/molly_gmail_action.py`
  - `scripts/molly_schedule_action.py gmail-*`로 위임하는 Gmail 호환 wrapper.

- `scripts/openclaw_create_event_bridge.py`
  - 초기 OpenClaw create-only bridge용 entrypoint.
  - 현재 live 경로에서는 OpenClaw가 `molly_schedule_action.py`를 직접 호출하는 방식을 우선한다.

- `scripts/molly_core_execute.py`
  - structured JSON request 실행용 하위 호환 경계.
  - 새 OpenClaw exec 명령은 가능한 한 `molly_schedule_action.py`를 사용한다.

- `bot.py`
  - legacy direct Telegram polling runtime.
  - production Telegram 대화는 OpenClaw gateway를 사용한다.
  - emergency fallback으로 실행할 때만 `MOLLY_LEGACY_TELEGRAM_BOT_ENABLED=1`을 명시한다.

- `calendar_client.py`
  - `calendar_repository.py`로 넘어간 뒤 남은 legacy import shim.
  - 새 코드는 직접 import하지 않는다.

## Cleanup rule

호환 entrypoint를 제거하기 전에는 다음 조건을 확인한다.

1. 문서와 OpenClaw workspace instructions가 canonical entrypoint만 참조한다.
2. 관련 테스트가 canonical entrypoint 기준으로 이전되어 있다.
3. command journal 또는 운영 로그에서 최근 사용 흔적이 없다.
4. 제거 후 `pytest`와 실제 `molly_schedule_action.py` smoke test가 통과한다.
