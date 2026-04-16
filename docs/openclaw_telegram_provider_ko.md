# OpenClaw Telegram Provider

## 목표

Telegram 자연어 요청을 휴리스틱만으로 해석하는 한계를 줄이기 위해, OpenClaw가 먼저 구조화된 draft를 만들어 주고 Molly의 deterministic Python 로직이 그 draft를 검증하고 실행하는 흐름을 추가했습니다.

## 현재 흐름

현재 Telegram 자연어 처리 흐름은 아래와 같습니다.

1. 사용자가 Telegram으로 자연어 메시지를 보냅니다.
2. Molly는 설정에 따라 OpenClaw extractor를 먼저 시도합니다.
3. OpenClaw가 구조화 draft를 반환하면 `telegram_nlu.py`가 그 draft를 기존 intent 모델로 변환합니다.
4. 필수 정보가 부족하면 Molly가 다시 되묻습니다.
5. 최종 실행은 여전히 deterministic Python 캘린더 로직이 담당합니다.
6. OpenClaw가 실패하거나 응답이 비정상이면 기존 휴리스틱 NLU로 자동 fallback 됩니다.

## 추가된 구성

- `openclaw_telegram_provider.py`
  - OpenAI-compatible HTTP endpoint 호출
  - JSON 응답 파싱
  - `ExtractedTelegramDraft` 변환
- `telegram_extractor_provider.py`
  - 설정값을 읽어 실제 extractor를 선택
- `bot.py`
  - 시작 시 extractor를 등록하고, 없으면 휴리스틱 fallback으로 동작
- `config.py`
  - extractor backend와 OpenClaw endpoint 설정 추가

## 설정값

아래 환경변수를 사용합니다.

- `MOLLY_TELEGRAM_EXTRACTOR_BACKEND`
  - `heuristic` 또는 `openclaw`
- `OPENCLAW_API_URL`
  - OpenAI-compatible chat completion endpoint URL
- `OPENCLAW_MODEL`
  - 사용할 모델 이름
- `OPENCLAW_API_KEY`
  - 필요한 경우에만 사용
- `OPENCLAW_TIMEOUT_SECONDS`
  - 기본값 `20`

## 중요한 설계 원칙

- OpenClaw는 해석 보조 역할만 맡습니다.
- 캘린더 생성/수정/삭제의 최종 실행은 Python 로직이 담당합니다.
- OpenClaw 응답이 틀리거나 모호해도, 곧바로 잘못된 일정이 반영되지 않도록 clarification과 deterministic validation을 유지합니다.

## 남아 있는 점

- 실제 OpenClaw endpoint URL과 model 이름은 환경에 맞게 `.env`에서 채워야 합니다.
- 아직 이메일 extraction 쪽에는 같은 수준의 실 provider 연결이 들어가 있지 않습니다.

## 다음 단계

다음으로는 실제 로컬 OpenClaw endpoint 설정을 붙이고, Telegram에서 몇 가지 실사용 문장을 기준으로 추출 품질을 확인하면서 prompt와 schema를 다듬는 단계가 적절합니다.
