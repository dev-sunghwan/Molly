# OpenClaw Exec Tool Strategy

## 왜 방향을 수정했는가

실제 OpenClaw Telegram 세션 로그를 확인해보니, OpenClaw는 텔레그램 대화 안에서 이미 다음과 같은 도구를 자연스럽게 사용하고 있었다.

- `memory_search`
- `read`
- `write`
- `exec`

반면 로컬 셸에서 직접 시도한 `openclaw infer ...` / `openclaw agent ...` one-shot 호출은 현재 환경에서 안정적으로 반환되지 않았다.

즉 현재 기준에서 더 신뢰할 수 있는 실행 표면은:

- 추측한 inference CLI 경로가 아니라
- OpenClaw가 실제 대화 중에 사용하는 `exec` 도구

이다.

## 전략

따라서 Molly 연동의 첫 실전 경로는 아래처럼 정리한다.

`Telegram -> OpenClaw conversation -> OpenClaw exec tool -> Molly Core CLI -> Local calendar DB`

이 구조에서는 OpenClaw가:

1. 사용자 말을 이해하고
2. 필요한 정보가 부족하면 clarification 하고
3. 정보가 다 모이면
4. `exec` 도구로 Molly Core 실행 스크립트를 호출한다

## 이번 단계에서 추가한 것

OpenClaw의 `exec` 사용 습관에 맞추기 위해 shell-friendly argv 스크립트를 추가했다.

- `scripts/molly_create_event.py`

이 스크립트는 stdin JSON 대신 명시적 플래그를 받는다.

예:

```bash
./.venv/bin/python scripts/molly_create_event.py \
  --calendar younha \
  --title "Tennis" \
  --date 2026-04-16 \
  --start 17:00 \
  --end 18:00 \
  --raw-input "내일 오후 5시에 윤하 테니스 넣어줘"
```

## 왜 이 방식이 좋은가

- OpenClaw `exec` 도구에서 호출하기 쉽다
- heredoc/stdin JSON보다 디버깅이 쉽다
- 일정 생성 명령을 명시적으로 볼 수 있다
- Molly Core의 deterministic validation은 그대로 유지된다

## OpenClaw 쪽에서 기대하는 동작

OpenClaw는 먼저 내부적으로 구조화 요청을 완성한 뒤, 다음과 같은 명령을 만들면 된다.

```bash
./.venv/bin/python scripts/molly_create_event.py \
  --calendar younha \
  --title "Tennis" \
  --date 2026-04-16 \
  --start 18:30 \
  --end 20:00 \
  --raw-input "내일 오후 6시 반부터 8시까지 윤하 테니스로 일정 넣어줘"
```

실행 결과는 JSON으로 받는다.

## 현재 결론

Molly 연동의 첫 실제 live 경로는 `infer model run` 고정이 아니라, OpenClaw가 이미 잘 쓰고 있는 `exec` 도구를 경유하는 방식이 더 현실적이다.

다음 단계는 OpenClaw에게 이 실행 패턴을 실제로 따르게 만들고, Saekomm 대화에서 end-to-end로 일정 생성이 되는지 확인하는 것이다.

## Python 환경 주의사항

Saekomm 실대화 로그를 다시 확인한 결과, OpenClaw는 Molly 실행 명령 자체는 올바르게 만들었지만 다음과 같이 시스템 `python3`를 사용했다.

```bash
python3 /home/sunghwan/projects/Molly/scripts/molly_create_event.py ...
```

이 호출은 아래 오류로 실패했다.

```text
ModuleNotFoundError: No module named 'dotenv'
```

원인은 Molly 의존성이 없어서가 아니라, 잘못된 인터프리터를 사용했기 때문이다.

- `pyproject.toml`에는 `python-dotenv`가 명시되어 있다
- Molly의 `.venv` 안에는 `python-dotenv`가 실제로 설치되어 있다
- 시스템 `python3` 쪽은 Molly 프로젝트 실행 환경이 아니다

따라서 OpenClaw가 Molly를 호출할 때는 항상 프로젝트 가상환경 파이썬을 사용해야 한다.

권장 명령은 다음 둘 중 하나다.

```bash
/home/sunghwan/projects/Molly/.venv/bin/python /home/sunghwan/projects/Molly/scripts/molly_create_event.py ...
```

또는 작업 디렉터리가 Molly 프로젝트 루트일 때:

```bash
./.venv/bin/python scripts/molly_create_event.py ...
```

이 규칙은 선택사항이 아니라 현재 기준의 필수 실행 규칙이다. Saekomm live 검증은 이 `.venv` 기반 실행 패턴을 전제로 다시 시도해야 한다.
