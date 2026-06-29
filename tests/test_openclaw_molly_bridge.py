from pathlib import Path

from openclaw_molly_bridge import (
    _parse_json_output,
    build_create_event_prompt,
    build_exec_tool_command,
    run_create_event_bridge,
)


def test_build_create_event_prompt_mentions_required_schema():
    prompt = build_create_event_prompt("내일 오후 5시에 윤하 테니스 넣어줘")

    assert "create_event" in prompt
    assert "target_calendar" in prompt
    assert "YYYY-MM-DD" in prompt
    assert "Telegram message" in prompt
    assert "Do not guess or default a time" in prompt


def test_run_create_event_bridge_executes_payload():
    def fake_infer(message_text: str) -> str:
        assert "윤하 테니스" in message_text
        return (
            '{"action":"create_event","target_calendar":"younha","title":"Tennis",'
            '"target_date":"2026-04-16","start_time":"17:00","end_time":"18:00",'
            '"all_day":false,"raw_input":"내일 오후 5시에 윤하 테니스 넣어줘"}'
        )

    def fake_execute(payload: dict) -> dict:
        assert payload["target_calendar"] == "younha"
        assert payload["action"] == "create_event"
        assert payload["request_id"] == "telegram:chat-1:msg-2"
        return {"success": True, "action": "create_event", "message": "ok"}

    result = run_create_event_bridge(
        "내일 오후 5시에 윤하 테니스 넣어줘",
        request_id="telegram:chat-1:msg-2",
        source="telegram",
        source_message_id="msg-2",
        source_user_id="user-1",
        infer_runner=fake_infer,
        execute_runner=fake_execute,
    )

    assert result["status"] == "executed"
    assert result["request"]["request_id"] == "telegram:chat-1:msg-2"
    assert result["request"]["source_message_id"] == "msg-2"
    assert result["request"]["source_user_id"] == "user-1"
    assert result["result"]["success"] is True


def test_run_create_event_bridge_surfaces_clarification():
    def fake_infer(message_text: str) -> str:
        return '{"status":"needs_clarification","reason":"target_calendar is missing"}'

    result = run_create_event_bridge(
        "내일 오후 5시에 테니스 넣어줘",
        infer_runner=fake_infer,
    )

    assert result["status"] == "needs_clarification"
    assert "target_calendar" in result["reason"]


def test_parse_json_output_strips_code_fence():
    payload = _parse_json_output("```json\n{\"status\":\"needs_clarification\"}\n```")

    assert payload["status"] == "needs_clarification"


def test_build_exec_tool_command_returns_shell_friendly_args():
    command = build_exec_tool_command(
        {
            "action": "create_event",
            "target_calendar": "younha",
            "title": "Tennis",
            "target_date": "2026-04-16",
            "start_time": "17:00",
            "end_time": "18:00",
            "raw_input": "내일 오후 5시에 윤하 테니스 넣어줘",
            "nlu": "openclaw",
            "request_source": "openclaw_exec_tool",
            "request_id": "telegram:chat-1:msg-2",
            "source": "telegram",
            "source_message_id": "msg-2",
        }
    )

    assert command[0] == str(Path.cwd() / ".venv" / "bin" / "python")
    assert "molly_schedule_action.py" in command[1]
    assert "create" in command
    assert "--calendar" in command
    assert "younha" in command
    assert "--title" in command
    assert "Tennis" in command
    assert "--request-id" in command
    assert "telegram:chat-1:msg-2" in command
    assert "--source-message-id" in command
    assert "msg-2" in command


def test_build_exec_tool_command_includes_end_date_when_present():
    command = build_exec_tool_command(
        {
            "action": "create_event",
            "target_calendar": "younha",
            "title": "Cub Indoor Camp",
            "target_date": "2026-04-17",
            "end_date": "2026-04-19",
            "start_time": "18:45",
            "end_time": "16:00",
        }
    )

    assert "--end-date" in command
    assert "2026-04-19" in command


def test_build_exec_tool_command_omits_end_when_missing():
    command = build_exec_tool_command(
        {
            "action": "create_event",
            "target_calendar": "family",
            "title": "Ferry",
            "target_date": "2026-04-16",
            "start_time": "17:00",
        }
    )

    assert "--start" in command
    assert "17:00" in command
    assert "--end" not in command
