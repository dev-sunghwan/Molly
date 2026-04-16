# OpenClaw CLI Bridge For Create Event

## 목적

이 단계의 목적은 OpenClaw가 해석한 `create_event` 요청을 Molly Core의 deterministic execution layer로 넘길 수 있는 첫 번째 실제 브리지를 만드는 것이다.

## 현재 범위

이번 브리지는 의도적으로 범위를 좁게 잡는다.

- action: `create_event`
- 입력: Telegram 자연어 1건
- OpenClaw 출력: 구조화된 JSON request
- Molly Core 입력: 구조화된 JSON request
- 최종 실행: 로컬 캘린더 DB 반영

즉, 이번 단계는 OpenClaw와 Molly Core 사이의 첫 “실행 배관”을 만든 단계다.

## 추가된 구성

- `openclaw_molly_bridge.py`
  - OpenClaw extraction prompt 생성
  - OpenClaw 결과 JSON 파싱
  - Molly Core CLI 실행 연결
- `scripts/openclaw_create_event_bridge.py`
  - 메시지 1건을 받아 브리지를 한 번 실행하는 entrypoint
- `tests/test_openclaw_molly_bridge.py`
  - 브리지 동작과 clarification 경로 검증

## 현재 구조

현재 브리지 흐름은 아래와 같다.

`message text -> OpenClaw inference -> structured JSON -> Molly Core CLI -> execution result`

OpenClaw가 반환해야 하는 구조화 요청 예시는 아래와 같다.

```json
{
  "action": "create_event",
  "target_calendar": "younha",
  "title": "Tennis",
  "target_date": "2026-04-16",
  "start_time": "17:00",
  "end_time": "18:00",
  "all_day": false,
  "raw_input": "내일 오후 5시에 윤하 테니스 넣어줘",
  "nlu": "openclaw",
  "request_source": "openclaw_cli_bridge"
}
```

정보가 부족한 경우에는 실행 요청 대신 clarification 응답을 반환하도록 했다.

예:

```json
{
  "status": "needs_clarification",
  "reason": "target_calendar is missing"
}
```

## 중요한 점

이번 브리지는 “OpenClaw invocation 인자까지 완전히 확정된 최종판”은 아니다.

현재 로컬 OpenClaw runtime의 inference CLI 표면은 일부 확인되었지만, 실제 `model run`의 최종 인자 조합은 아직 추가 검증이 필요하다. 그래서 현재 구현은:

- OpenClaw 호출 계층
- Molly Core 실행 계층

을 분리해두고, OpenClaw 호출 커맨드만 한 곳에서 조정할 수 있게 만들었다.

## 왜 이 단계가 의미가 있는가

이제 Molly 쪽은 더 이상 Telegram bot 내부에 실행 로직을 묶어둘 필요가 없다.

OpenClaw가 어떤 방식으로 JSON request를 생산하든, Molly Core는 같은 실행 표면을 사용할 수 있다.

즉 다음 단계부터는:

- OpenClaw CLI 실제 인자 보정
- OpenClaw tool/capability 연동 전환

중 어느 방향으로 가더라도 Molly Core 쪽은 거의 바뀌지 않는다.

## 다음 단계

다음 단계는 실제 로컬 OpenClaw runtime에 맞춰 `infer/model run` 호출 인자를 확정하고, `create_event` 1건을 OpenClaw 대화에서 Molly Core 실행까지 end-to-end로 검증하는 것이다.
