import pytest

import config
from assistant_workflow import CandidateStatus, build_candidate_from_email, build_intent_resolution
from email_extraction import ExtractedEventDraft
from gmail_adapter import GmailMessage
from intent_models import ResolutionStatus


@pytest.fixture(autouse=True)
def _clear_gmail_allowlist(monkeypatch):
    monkeypatch.setattr(config, "GMAIL_ALLOWED_SENDERS", set())


def test_email_candidate_ready_when_calendar_and_date_are_present():
    message = GmailMessage(
        message_id="msg-1",
        thread_id="thr-1",
        subject="YounHa concert",
        sender="teacher@example.com",
        snippet="YounHa concert tomorrow 18:00",
        body_text="YounHa concert tomorrow 18:00 at school hall.",
        internal_date=None,
        raw_payload={},
    )

    candidate = build_candidate_from_email(message)

    assert candidate.status == CandidateStatus.READY
    assert candidate.intent is not None
    assert candidate.intent.target_calendar == "younha"
    assert candidate.intent.target_date is not None
    assert candidate.intent.time_range is not None
    resolution = build_intent_resolution(candidate)
    assert resolution is not None
    assert resolution.status == ResolutionStatus.READY


def test_email_candidate_needs_clarification_when_calendar_missing():
    message = GmailMessage(
        message_id="msg-2",
        thread_id="thr-2",
        subject="Dentist reminder",
        sender="clinic@example.com",
        snippet="Dentist tomorrow 09:30",
        body_text="Dentist tomorrow 09:30.",
        internal_date=None,
        raw_payload={},
    )

    candidate = build_candidate_from_email(message)

    assert candidate.status == CandidateStatus.NEEDS_CLARIFICATION
    assert candidate.intent is not None
    assert candidate.intent.target_calendar is None
    assert "target_calendar" in candidate.missing_fields
    resolution = build_intent_resolution(candidate)
    assert resolution is not None
    assert resolution.status == ResolutionStatus.NEEDS_CLARIFICATION


def test_email_candidate_ignored_when_not_schedule_related():
    message = GmailMessage(
        message_id="msg-3",
        thread_id="thr-3",
        subject="Security alert",
        sender="no-reply@example.com",
        snippet="New sign-in on your account",
        body_text="We noticed a new sign-in on your account.",
        internal_date=None,
        raw_payload={},
    )

    candidate = build_candidate_from_email(message)

    assert candidate.status == CandidateStatus.IGNORED
    assert candidate.intent is None


def test_email_candidate_uses_extracted_draft_when_available():
    message = GmailMessage(
        message_id="msg-4",
        thread_id="thr-4",
        subject="FW: Registration Confirmation | AWS Summit London 2026",
        sender='"김성환(SungHwan Kim)" <sunghwan.k@hanwha.com>',
        snippet="AWS Summit London 2026",
        body_text="Registration Confirmation for AWS Summit London 2026.",
        internal_date=None,
        raw_payload={},
    )
    draft = ExtractedEventDraft(
        is_schedule_related=True,
        title="AWS Summit London 2026",
        target_calendar="sunghwan",
        target_date_text="tomorrow",
        time_text="09:00-17:00",
        confidence=0.92,
        reasoning="The email is a registration confirmation for an event and names SungHwan.",
    )

    candidate = build_candidate_from_email(message, extracted_draft=draft)

    assert candidate.status == CandidateStatus.READY
    assert candidate.intent is not None
    assert candidate.intent.target_calendar == "sunghwan"
    assert candidate.intent.time_range is not None
    assert candidate.intent.metadata["llm_confidence"] == 0.92


def test_email_candidate_can_ignore_with_extracted_draft():
    message = GmailMessage(
        message_id="msg-5",
        thread_id="thr-5",
        subject="Security alert",
        sender="no-reply@example.com",
        snippet="New sign-in detected",
        body_text="We noticed a new sign-in.",
        internal_date=None,
        raw_payload={},
    )
    draft = ExtractedEventDraft(
        is_schedule_related=False,
        reasoning="This is a security notification, not an event invitation or schedule change.",
    )

    candidate = build_candidate_from_email(message, extracted_draft=draft)

    assert candidate.status == CandidateStatus.IGNORED
    assert candidate.intent is None


def test_email_candidate_ignored_when_sender_not_in_allowlist(monkeypatch):
    monkeypatch.setattr(config, "GMAIL_ALLOWED_SENDERS", {"jylim3287@gmail.com"})
    message = GmailMessage(
        message_id="msg-6",
        thread_id="thr-6",
        subject="YounHa concert",
        sender="teacher@example.com",
        snippet="YounHa concert tomorrow 18:00",
        body_text="YounHa concert tomorrow 18:00 at school hall.",
        internal_date=None,
        raw_payload={},
    )

    candidate = build_candidate_from_email(message)

    assert candidate.status == CandidateStatus.IGNORED
    assert candidate.reason == "Sender is not in Molly's Gmail allowlist."
    assert candidate.intent is None


def test_email_candidate_allows_normalized_sender_from_header(monkeypatch):
    monkeypatch.setattr(config, "GMAIL_ALLOWED_SENDERS", {"jylim3287@gmail.com"})
    message = GmailMessage(
        message_id="msg-7",
        thread_id="thr-7",
        subject="YounHa concert",
        sender='"JiYoung" <jylim3287@gmail.com>',
        snippet="YounHa concert tomorrow 18:00",
        body_text="YounHa concert tomorrow 18:00 at school hall.",
        internal_date=None,
        raw_payload={},
    )

    candidate = build_candidate_from_email(message)

    assert candidate.status == CandidateStatus.READY
    assert candidate.intent is not None
    assert candidate.intent.metadata["email_sender_normalized"] == "jylim3287@gmail.com"


def test_forwarded_aws_email_extracts_real_event_date_and_time(monkeypatch):
    monkeypatch.setattr(config, "GMAIL_ALLOWED_SENDERS", {"sunghwan.k@hanwha.com"})
    monkeypatch.setattr("utils._today_local", lambda: __import__("datetime").date(2026, 4, 18))
    message = GmailMessage(
        message_id="msg-8",
        thread_id="thr-8",
        subject="FW: Registration Confirmation | AWS Summit London 2026",
        sender='"김성환(SungHwan Kim)" <sunghwan.k@hanwha.com>',
        snippet="Your confirmation of registration for AWS Summit London 2026.",
        body_text=(
            "From: Amazon Web Services <aws-marketing-email-replies@amazon.com>\n"
            "Sent: 25 March 2026 15:06\n"
            "Subject: Registration Confirmation | AWS Summit London 2026\n"
            "Thank you for registering for AWS Summit London\n"
            "Date\n"
            "April 22, 2026\n"
            "08:00 – 18:30 BST\n"
            "Location\n"
            "Excel London"
        ),
        internal_date=None,
        raw_payload={},
    )

    candidate = build_candidate_from_email(message)

    assert candidate.status == CandidateStatus.READY
    assert candidate.intent is not None
    assert candidate.intent.target_calendar == "sunghwan"
    assert candidate.intent.target_date.isoformat() == "2026-04-22"
    assert candidate.intent.time_range is not None
    assert candidate.intent.time_range.start == "08:00"
    assert candidate.intent.time_range.end == "18:30"


def test_forwarded_cubs_email_prefers_body_date_time_and_child_calendar(monkeypatch):
    monkeypatch.setattr(config, "GMAIL_ALLOWED_SENDERS", {"ray.sunghwan@gmail.com"})
    monkeypatch.setattr("utils._today_local", lambda: __import__("datetime").date(2026, 4, 18))
    message = GmailMessage(
        message_id="msg-9",
        thread_id="thr-9",
        subject="Fwd: Cubs on Monday (20th April)",
        sender="SungHwan Ray Kim <ray.sunghwan@gmail.com>",
        snippet="Cubs on Monday (20th April)",
        body_text=(
            "YounHa 스카우트인 Cubs 관련 일정이야.\n"
            "---------- Forwarded message ---------\n"
            "From: Graham Fairclough <myscout@onlinescoutmanager.co.uk>\n"
            "Date: Tue, 14 Apr 2026 at 16:54\n"
            "Subject: Cubs on Monday (20th April)\n"
            "Please note that next Monday evening, we will be holding the Cub evening at\n"
            "Green Lane Primary School - 6.30pm - 8pm.\n"
            "No uniform is required but please wear clothes that are suitable for the weather.\n"
        ),
        internal_date=None,
        raw_payload={},
    )

    candidate = build_candidate_from_email(message)

    assert candidate.status == CandidateStatus.READY
    assert candidate.intent is not None
    assert candidate.intent.target_calendar == "younha"
    assert candidate.intent.target_date.isoformat() == "2026-04-20"
    assert candidate.intent.time_range is not None
    assert candidate.intent.time_range.start == "18:30"
    assert candidate.intent.time_range.end == "20:00"
