import json

import pytest

import config
import state_store
from intent_models import (
    IntentAction,
    IntentResolution,
    IntentSource,
    ResolutionStatus,
    ScheduleIntent,
)
from scripts import molly_core_execute


def test_molly_core_execute_journals_structured_request(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    monkeypatch.setattr(config, "validate", lambda: None)

    class DummyRepo:
        @classmethod
        def from_config(cls):
            return cls()

    class DummyCore:
        def __init__(self, calendar_repo):
            self.calendar_repo = calendar_repo

        def execute_resolution(self, resolution):
            assert resolution.intent.title == "Tennis"
            return "ok"

    def fake_resolution_from_request(payload):
        return IntentResolution(
            status=ResolutionStatus.READY,
            intent=ScheduleIntent(
                action=IntentAction.CREATE_EVENT,
                source=IntentSource.TELEGRAM_FREE_TEXT,
                raw_input=payload["raw_input"],
                target_calendar="younha",
                title="Tennis",
            ),
        )

    payload = {
        "request_id": "req-core-1",
        "source": "telegram",
        "source_message_id": "msg-2",
        "action": "create_event",
        "raw_input": "내일 윤하 테니스",
    }
    monkeypatch.setattr("sys.stdin", _StringInput(json.dumps(payload)))
    monkeypatch.setattr(molly_core_execute, "CalendarRepository", DummyRepo)
    monkeypatch.setattr(molly_core_execute, "MollyCore", DummyCore)
    monkeypatch.setattr(molly_core_execute, "resolution_from_request", fake_resolution_from_request)

    molly_core_execute.main()

    output = json.loads(capsys.readouterr().out)
    assert output["success"] is True
    stored = state_store.get_command_by_request_id("req-core-1")
    assert stored is not None
    assert stored["source"] == "telegram"
    assert stored["source_message_id"] == "msg-2"
    assert stored["raw_text"] == "내일 윤하 테니스"
    assert stored["status"] == "executed"
    assert stored["structured_payload"]["action"] == "create_event"
    assert stored["execution_result"]["success"] is True


def test_molly_core_execute_marks_validation_errors_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    monkeypatch.setattr(config, "validate", lambda: None)

    payload = {
        "request_id": "req-core-invalid",
        "source": "telegram",
        "action": "search",
        "query": "Tennis",
        "python": "import sqlite3",
    }
    monkeypatch.setattr("sys.stdin", _StringInput(json.dumps(payload)))

    with pytest.raises(ValueError):
        molly_core_execute.main()

    stored = state_store.get_command_by_request_id("req-core-invalid")
    assert stored is not None
    assert stored["status"] == "rejected"
    assert "Unsupported field" in stored["validation_error"] or "Unsafe field" in stored["validation_error"]
    assert stored["execution_result"]["success"] is False


def test_molly_core_execute_replays_completed_request_without_execution(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    state_store.init_db()
    state_store.record_inbound_command(
        request_id="req-core-replay",
        source="telegram",
        raw_payload={"request_id": "req-core-replay", "action": "search"},
        raw_text="tennis",
    )
    state_store.update_command_status(
        "req-core-replay",
        "executed",
        execution_result={
            "success": True,
            "action": "search",
            "message": "cached result",
        },
    )

    payload = {
        "request_id": "req-core-replay",
        "source": "telegram",
        "action": "search",
        "query": "Tennis",
    }
    monkeypatch.setattr("sys.stdin", _StringInput(json.dumps(payload)))
    monkeypatch.setattr(
        molly_core_execute,
        "resolution_from_request",
        lambda _payload: (_ for _ in ()).throw(AssertionError("should not parse")),
    )

    molly_core_execute.main()

    output = json.loads(capsys.readouterr().out)
    stored = state_store.get_command_by_request_id("req-core-replay")
    assert output["message"] == "cached result"
    assert stored["status"] == "executed"


def test_molly_core_execute_requires_request_id_for_mutations_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    monkeypatch.setattr(config, "REQUIRE_REQUEST_ID_FOR_MUTATIONS", True)
    monkeypatch.setattr(molly_core_execute.uuid, "uuid4", lambda: "fixed")
    monkeypatch.setattr(
        molly_core_execute,
        "resolution_from_request",
        lambda _payload: (_ for _ in ()).throw(AssertionError("should not parse")),
    )

    payload = {
        "source": "telegram",
        "action": "create_event",
        "raw_input": "내일 윤하 테니스",
    }
    monkeypatch.setattr("sys.stdin", _StringInput(json.dumps(payload)))

    with pytest.raises(ValueError):
        molly_core_execute.main()

    stored = state_store.get_command_by_request_id("molly-core-fixed")
    assert stored is not None
    assert stored["status"] == "rejected"
    assert "Stable request_id is required" in stored["validation_error"]


class _StringInput:
    def __init__(self, value: str) -> None:
        self.value = value

    def read(self, *args, **kwargs):
        return self.value
