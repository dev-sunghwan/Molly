import subprocess
import sys

import pytest

import config
import state_store
from scripts import molly_schedule_action


def test_molly_schedule_action_view_help():
    result = subprocess.run(
        [sys.executable, "scripts/molly_schedule_action.py", "view", "--help"],
        cwd="/home/sunghwan/projects/Molly",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--scope" in result.stdout
    assert "--actor-user-id" in result.stdout
    assert "--actor-name" in result.stdout


def test_molly_schedule_action_search_help():
    result = subprocess.run(
        [sys.executable, "scripts/molly_schedule_action.py", "search", "--help"],
        cwd="/home/sunghwan/projects/Molly",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--query" in result.stdout
    assert "--actor-name" in result.stdout


def test_molly_schedule_action_create_help_shows_recurrence_options():
    result = subprocess.run(
        [sys.executable, "scripts/molly_schedule_action.py", "create", "--help"],
        cwd="/home/sunghwan/projects/Molly",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--recurrence" in result.stdout
    assert "--weekly-day" in result.stdout
    assert "--actor-user-id" in result.stdout
    assert "--actor-name" in result.stdout


def test_molly_schedule_action_gmail_confirm_help():
    result = subprocess.run(
        [sys.executable, "scripts/molly_schedule_action.py", "gmail-confirm", "--help"],
        cwd="/home/sunghwan/projects/Molly",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--candidate-id" in result.stdout
    assert "--actor-user-id" in result.stdout
    assert "--actor-name" in result.stdout


def test_molly_schedule_action_view_help_lists_core_scopes():
    result = subprocess.run(
        [sys.executable, "scripts/molly_schedule_action.py", "view", "--help"],
        cwd="/home/sunghwan/projects/Molly",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "week_next" in result.stdout
    assert "month_next" in result.stdout


def test_molly_schedule_action_command_help():
    result = subprocess.run(
        [sys.executable, "scripts/molly_schedule_action.py", "command", "--help"],
        cwd="/home/sunghwan/projects/Molly",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--text" in result.stdout
    assert "actor-user-id" in result.stdout


def test_molly_schedule_action_journals_command(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")

    monkeypatch.setattr(
        molly_schedule_action,
        "_execute_command_text",
        lambda text, actor_user_id=None, actor_name=None: {
            "success": True,
            "action": "view_daily",
            "message": "ok",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "molly_schedule_action.py",
            "command",
            "--text",
            "today",
            "--request-id",
            "req-command-1",
            "--source",
            "telegram",
            "--source-message-id",
            "msg-1",
        ],
    )

    molly_schedule_action.main()

    stored = state_store.get_command_by_request_id("req-command-1")
    assert stored is not None
    assert stored["source"] == "telegram"
    assert stored["source_message_id"] == "msg-1"
    assert stored["raw_text"] == "today"
    assert stored["status"] == "executed"
    assert stored["execution_result"]["success"] is True


def test_molly_schedule_action_journals_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")

    monkeypatch.setattr(
        molly_schedule_action,
        "_execute_payload",
        lambda payload, actor_user_id=None, actor_name=None: {
            "success": True,
            "action": payload["action"],
            "message": "ok",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "molly_schedule_action.py",
            "search",
            "--query",
            "tennis",
            "--request-id",
            "req-search-1",
            "--source",
            "slack",
            "--actor-user-id",
            "123",
            "--actor-name",
            "Admin",
        ],
    )

    molly_schedule_action.main()

    stored = state_store.get_command_by_request_id("req-search-1")
    assert stored is not None
    assert stored["source"] == "slack"
    assert stored["source_user_id"] == "123"
    assert stored["source_user_name"] == "Admin"
    assert stored["raw_payload"]["action"] == "search"
    assert stored["raw_payload"]["query"] == "tennis"
    assert stored["status"] == "executed"
    assert stored["structured_payload"]["action"] == "search"


def test_molly_schedule_action_marks_value_errors_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")

    def raise_value_error(payload, actor_user_id=None, actor_name=None):
        raise ValueError("Unsupported field(s) for search: python")

    monkeypatch.setattr(molly_schedule_action, "_execute_payload", raise_value_error)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "molly_schedule_action.py",
            "search",
            "--query",
            "tennis",
            "--request-id",
            "req-search-invalid",
            "--source",
            "slack",
        ],
    )

    with pytest.raises(ValueError):
        molly_schedule_action.main()

    stored = state_store.get_command_by_request_id("req-search-invalid")
    assert stored is not None
    assert stored["status"] == "rejected"
    assert "Unsupported field" in stored["validation_error"]
    assert stored["execution_result"]["success"] is False


def test_molly_schedule_action_replays_completed_request_without_execution(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    state_store.init_db()
    state_store.record_inbound_command(
        request_id="req-command-replay",
        source="telegram",
        raw_text="today",
        raw_payload={"subcommand": "command", "text": "today"},
    )
    state_store.update_command_status(
        "req-command-replay",
        "executed",
        execution_result={
            "success": True,
            "action": "view_daily",
            "message": "cached today",
        },
    )
    monkeypatch.setattr(
        molly_schedule_action,
        "_execute_command_text",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not execute")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "molly_schedule_action.py",
            "command",
            "--text",
            "today",
            "--request-id",
            "req-command-replay",
            "--source",
            "telegram",
        ],
    )

    molly_schedule_action.main()

    stored = state_store.get_command_by_request_id("req-command-replay")
    assert stored["status"] == "executed"
    assert stored["execution_result"]["message"] == "cached today"


def test_molly_schedule_action_requires_request_id_for_mutations_when_enabled(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    monkeypatch.setattr(config, "REQUIRE_REQUEST_ID_FOR_MUTATIONS", True)
    monkeypatch.setattr(molly_schedule_action.uuid, "uuid4", lambda: "fixed")
    monkeypatch.setattr(
        molly_schedule_action,
        "_execute_payload",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not execute")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "molly_schedule_action.py",
            "create",
            "--calendar",
            "younha",
            "--title",
            "Tennis",
            "--date",
            "2026-04-24",
            "--start",
            "17:00",
            "--end",
            "18:00",
        ],
    )

    with pytest.raises(ValueError):
        molly_schedule_action.main()

    stored = state_store.get_command_by_request_id("molly-cli-fixed")
    assert stored is not None
    assert stored["status"] == "rejected"
    assert "Stable request_id is required" in stored["validation_error"]


def test_execute_command_text_uses_free_text_nlu_for_explicit_month():
    result = molly_schedule_action._execute_command_text("show me July schedule")
    assert result["success"] is True
    assert result["action"] == "view_range"
    assert "📅 July 2026" in result["message"]
