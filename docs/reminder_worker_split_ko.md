# Reminder Worker 분리

## 왜 필요한가

기존 Molly 구조에서는 `bot.py`가 두 역할을 같이 맡고 있었다.

- Telegram 메시지 수신
- scheduler 기반 reminder / daily summary / tomorrow summary 실행

하지만 현재 방향은 다음과 같다.

`Telegram -> OpenClaw -> Molly Core -> Local Calendar DB`

이 구조에서는 더 이상 `bot.py`를 상시 실행하지 않아도 되므로, 기존처럼 scheduler를 `bot.py` 안에서만 시작하면 reminder 기능이 꺼진다.

즉 문제는 reminder 로직이 사라진 것이 아니라, 실행 주체가 더 이상 없다는 점이었다.

## 이번 단계에서 한 일

새 엔트리포인트를 추가했다.

- `scripts/run_reminder_worker.py`

이 worker는:

1. 설정과 상태 DB를 초기화하고
2. calendar backend에 연결하고
3. Telegram `Bot` 인스턴스를 만들고
4. 기존 `scheduler.py`의 job들을 시작한 뒤
5. 독립 프로세스로 계속 대기한다

## 현재 구조

이제 역할 분리는 아래처럼 정리된다.

- OpenClaw / Saekomm: 대화, 자연어 이해, clarification
- Molly Core: deterministic 일정 실행
- Reminder Worker: reminder / daily summary / tomorrow summary 발송

즉 `bot.py`는 더 이상 필수 상시 프로세스가 아니고, reminder 기능은 별도 worker로 유지된다.

## 실행 방법

실제 장기 실행:

```bash
./.venv/bin/python scripts/run_reminder_worker.py
```

짧은 시작 점검만 할 때:

```bash
./.venv/bin/python scripts/run_reminder_worker.py --startup-check
```

## 의미

이 분리는 단순한 편의가 아니라 새 구조에 맞는 책임 분리다.

- 대화 UI와 background jobs를 분리할 수 있다
- OpenClaw 교체/변경과 reminder runtime이 독립적이다
- Molly Core는 계속 deterministic execution layer로 남는다
- 나중에 systemd, tmux, supervisor 같은 방식으로 worker만 따로 운영하기 쉬워진다
