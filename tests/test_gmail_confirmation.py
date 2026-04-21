from datetime import date

import config
import gmail_confirmation
import state_store
from intent_models import IntentAction


class FakeRepo:
    def add_event(self, command):
        return f"Added to YounHa: {command['title']}"


def setup_function():
    if config.STATE_DB_PATH.exists():
        config.STATE_DB_PATH.unlink()
    state_store.init_db()


def _candidate_payload():
    return {
        "status": "ready",
        "message_id": "msg-1",
        "reason": "Ready",
        "summary": "Alpha-Math | calendar=younha | date=2026-04-17 | time=17:00-18:00",
        "missing_fields": [],
        "intent": {
            "action": "create_event",
            "source": "email",
            "raw_input": "Email body",
            "target_calendar": "younha",
            "title": "Alpha-Math",
            "target_date": date(2026, 4, 17).isoformat(),
            "date_range": None,
            "time_range": {"start": "17:00", "end": "18:00"},
            "recurrence": [],
            "search_query": None,
            "help_topic": None,
            "limit": None,
            "changes": {},
            "metadata": {"email_message_id": "msg-1"},
        },
    }


def test_format_candidate_confirmation_contains_reply_commands():
    candidate_id = state_store.save_email_candidate(
        message_id="msg-1",
        status="ready",
        reason="Ready",
        summary="Alpha-Math | calendar=younha",
        candidate_payload=_candidate_payload(),
        metadata={"subject": "Registration", "sender": "ray.sunghwan@gmail.com"},
    )
    stored = state_store.get_email_candidate(candidate_id)

    message = gmail_confirmation.format_candidate_confirmation(stored)

    assert f"Gmail candidate #{candidate_id}" in message
    assert f"gmail confirm {candidate_id}" in message
    assert f"gmail ignore {candidate_id}" in message


def test_ignore_candidate_updates_decision_status():
    candidate_id = state_store.save_email_candidate(
        message_id="msg-2",
        status="ready",
        reason="Ready",
        summary="Alpha-Math",
        candidate_payload=_candidate_payload(),
        metadata={},
    )

    result = gmail_confirmation.ignore_candidate(candidate_id, actor_user_id=123)

    stored = state_store.get_email_candidate(candidate_id)
    assert "Ignored Gmail candidate" in result
    assert stored is not None
    assert stored["decision_status"] == "ignored"
    assert stored["metadata"]["ignored_by_user_id"] == 123


def test_confirm_candidate_executes_and_marks_executed():
    candidate_id = state_store.save_email_candidate(
        message_id="msg-3",
        status="ready",
        reason="Ready",
        summary="Alpha-Math",
        candidate_payload=_candidate_payload(),
        metadata={},
    )

    result = gmail_confirmation.confirm_candidate(candidate_id, FakeRepo(), actor_user_id=123)

    stored = state_store.get_email_candidate(candidate_id)
    assert f"Gmail candidate #{candidate_id}" in result
    assert "Added to YounHa: Alpha-Math" in result
    assert stored is not None
    assert stored["decision_status"] == "executed"
