import json
import sys

import config
import state_store
from scripts import molly_admin


def test_molly_admin_summary(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    state_store.init_db()
    state_store.record_inbound_command(
        request_id="req-summary-1",
        source="telegram",
        raw_text="today",
        raw_payload={"text": "today"},
    )
    state_store.enqueue_google_sync(
        operation="create",
        payload={"action": "create_event", "target_calendar": "family", "title": "Picnic"},
    )
    monkeypatch.setattr(sys, "argv", ["molly_admin.py", "summary"])

    molly_admin.main()

    output = json.loads(capsys.readouterr().out)
    assert output["success"] is True
    assert output["commands_by_status"] == {"received": 1}
    assert output["google_sync_by_status"] == {"pending": 1}


def test_molly_admin_commands_hides_text_and_payload_by_default(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    state_store.init_db()
    state_store.record_inbound_command(
        request_id="req-hidden-1",
        source="slack",
        raw_text="private family schedule",
        raw_payload={"text": "private family schedule", "token": "secret-token"},
    )
    monkeypatch.setattr(sys, "argv", ["molly_admin.py", "commands"])

    molly_admin.main()

    command = json.loads(capsys.readouterr().out)["commands"][0]
    assert command["request_id"] == "req-hidden-1"
    assert "raw_text" not in command
    assert "raw_payload" not in command


def test_molly_admin_command_can_include_redacted_payload(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    state_store.init_db()
    state_store.record_inbound_command(
        request_id="req-redact-1",
        source="slack",
        raw_text="today",
        raw_payload={
            "action": "view",
            "token": "secret-token",
            "nested": {"client_secret": "secret"},
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "molly_admin.py",
            "command",
            "--request-id",
            "req-redact-1",
            "--include-payload",
        ],
    )

    molly_admin.main()

    command = json.loads(capsys.readouterr().out)["command"]
    assert command["raw_payload"]["action"] == "view"
    assert command["raw_payload"]["token"] == "[REDACTED]"
    assert command["raw_payload"]["nested"]["client_secret"] == "[REDACTED]"


def test_molly_admin_sync_lists_outbox_without_payload_by_default(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    state_store.init_db()
    state_store.enqueue_google_sync(
        operation="create",
        payload={"action": "create_event", "target_calendar": "family", "title": "Picnic"},
    )
    monkeypatch.setattr(sys, "argv", ["molly_admin.py", "sync", "--status", "pending"])

    molly_admin.main()

    outbox = json.loads(capsys.readouterr().out)["outbox"][0]
    assert outbox["operation"] == "create"
    assert outbox["status"] == "pending"
    assert "payload" not in outbox


def test_molly_admin_resend_sends_stored_execution_result(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "test-token")
    state_store.init_db()
    state_store.record_inbound_command(
        request_id="telegram:telegram:123:456",
        source="telegram",
        source_channel_id="telegram:123",
        source_message_id="456",
        raw_text="create test",
        raw_payload={"action": "create_event"},
    )
    state_store.update_command_status(
        "telegram:telegram:123:456",
        "executed",
        execution_result={"success": True, "message": "✅ Added test event"},
    )
    sent = []

    async def fake_send(chat_id, message):
        sent.append((chat_id, message))

    monkeypatch.setattr(molly_admin, "_send_telegram_message", fake_send)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "molly_admin.py",
            "resend",
            "--request-id",
            "telegram:telegram:123:456",
        ],
    )

    molly_admin.main()

    output = json.loads(capsys.readouterr().out)
    stored = state_store.get_command_by_request_id("telegram:telegram:123:456")
    assert output["success"] is True
    assert output["reply_status"] == "resent"
    assert output["reply_attempts"] == 1
    assert sent == [(123, "✅ Added test event")]
    assert stored["reply_status"] == "resent"
    assert stored["reply_attempts"] == 1


def test_molly_admin_resend_records_send_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    state_store.init_db()
    state_store.record_inbound_command(
        request_id="telegram:123:789",
        source="telegram",
        source_channel_id="telegram:123",
        raw_text="create test",
        raw_payload={"action": "create_event"},
    )
    state_store.update_command_status(
        "telegram:123:789",
        "executed",
        execution_result={"success": True, "message": "ok"},
    )

    async def fake_send(chat_id, message):
        raise RuntimeError("network down")

    monkeypatch.setattr(molly_admin, "_send_telegram_message", fake_send)
    monkeypatch.setattr(
        sys,
        "argv",
        ["molly_admin.py", "resend", "--request-id", "telegram:123:789"],
    )

    molly_admin.main()

    output = json.loads(capsys.readouterr().out)
    stored = state_store.get_command_by_request_id("telegram:123:789")
    assert output["success"] is False
    assert output["reply_status"] == "resend_failed"
    assert "RuntimeError: network down" in output["message"]
    assert stored["reply_status"] == "resend_failed"
    assert stored["reply_attempts"] == 1


def test_molly_admin_resend_rejects_non_telegram_without_force(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    state_store.init_db()
    state_store.record_inbound_command(
        request_id="slack-1",
        source="slack",
        raw_text="today",
        raw_payload={"text": "today"},
    )
    state_store.update_command_status(
        "slack-1",
        "executed",
        execution_result={"success": True, "message": "ok"},
    )
    monkeypatch.setattr(sys, "argv", ["molly_admin.py", "resend", "--request-id", "slack-1"])

    molly_admin.main()

    output = json.loads(capsys.readouterr().out)
    assert output["success"] is False
    assert "non-telegram" in output["message"]


def test_molly_admin_recover_replies_resends_missing_rows(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "test-token")
    state_store.init_db()
    state_store.record_inbound_command(
        request_id="telegram:123:456",
        source="telegram",
        source_channel_id="telegram:123",
        raw_text="create test",
        raw_payload={"action": "create_event"},
    )
    state_store.update_command_status(
        "telegram:123:456",
        "executed",
        execution_result={"success": True, "message": "✅ Added test event"},
    )
    sent = []

    async def fake_send(chat_id, message):
        sent.append((chat_id, message))

    monkeypatch.setattr(molly_admin, "_send_telegram_message", fake_send)
    monkeypatch.setattr(
        "scripts.molly_reply_tracker.send_and_track_reply",
        lambda **kwargs: __import__("asyncio").sleep(0, result=state_store.update_command_reply_status(kwargs["request_id"], "sent")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["molly_admin.py", "recover-replies", "--limit", "10"],
    )

    molly_admin.main()

    output = json.loads(capsys.readouterr().out)
    stored = state_store.get_command_by_request_id("telegram:123:456")
    assert output["success"] is True
    assert output["resent"] == ["telegram:123:456"]
    assert stored["reply_status"] == "sent"
    assert stored["reply_attempts"] == 1
