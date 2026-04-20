from telegram_extraction import build_extraction_prompt
from openclaw_telegram_provider import (
    _draft_from_payload,
    _extract_json_payload,
    extract_draft_via_openclaw,
)


def test_extract_json_payload_from_openai_style_response():
    response_payload = {
        "choices": [
            {
                "message": {
                    "content": (
                        "```json\n"
                        '{"action":"create_event","target_calendar":"윤하","title":"테니스","target_date_text":"내일","time_text":"오후 5시"}\n'
                        "```"
                    )
                }
            }
        ]
    }

    payload = _extract_json_payload(response_payload)

    assert payload is not None
    assert payload["action"] == "create_event"
    assert payload["target_calendar"] == "윤하"


def test_draft_from_payload_builds_structured_draft():
    draft = _draft_from_payload(
        {
            "action": "view_range",
            "target_date_text": "다음주",
            "limit": 5,
            "confidence": 0.91,
            "missing_fields": [],
        }
    )

    assert draft.action == "view_range"
    assert draft.target_date_text == "다음주"
    assert draft.limit == 5
    assert draft.confidence == 0.91


def test_extract_draft_via_openclaw_returns_none_on_invalid_payload():
    def fake_sender(prompt: str):
        assert "Telegram message" in prompt
        return {"choices": [{"message": {"content": "not json"}}]}

    draft = extract_draft_via_openclaw("윤하 테니스 넣어줘", sender=fake_sender)

    assert draft is None


def test_extract_draft_via_openclaw_returns_draft_on_valid_payload():
    def fake_sender(prompt: str):
        assert "윤하 테니스 넣어줘" in prompt
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"action":"create_event","target_calendar":"윤하",'
                            '"title":"테니스","target_date_text":"내일","time_text":"오후 5시"}'
                        )
                    }
                }
            ]
        }

    draft = extract_draft_via_openclaw("윤하 테니스 넣어줘", sender=fake_sender)

    assert draft is not None
    assert draft.action == "create_event"
    assert draft.target_calendar == "윤하"
    assert draft.title == "테니스"


def test_build_extraction_prompt_mentions_all_calendar_default_for_upcoming():
    prompt = build_extraction_prompt("Show me upcoming")

    assert "leave target_calendar empty" in prompt
    assert "all-calendars default" in prompt
