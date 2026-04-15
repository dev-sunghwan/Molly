import inbox_processor


class FakeService:
    pass


def test_format_processing_report_with_results():
    items = [
        inbox_processor.ProcessedMessage(
            message_id="1",
            status="ready",
            subject="YounHa concert",
            summary="YounHa concert | calendar=younha",
            skipped=False,
        ),
        inbox_processor.ProcessedMessage(
            message_id="2",
            status="ignored",
            subject="Security alert",
            summary="Message does not look scheduling-related.",
            skipped=True,
        ),
    ]

    report = inbox_processor.format_processing_report(items)

    assert "Processed inbox messages: 2" in report
    assert "READY | YounHa concert" in report
    assert "SKIP | Security alert" in report


def test_process_recent_inbox_messages_skips_previously_processed(monkeypatch):
    monkeypatch.setattr(
        inbox_processor.gmail_adapter,
        "list_message_ids",
        lambda service, max_results=10, query="in:inbox": ["msg-1"],
    )
    monkeypatch.setattr(
        inbox_processor.state_store,
        "init_db",
        lambda: None,
    )
    monkeypatch.setattr(
        inbox_processor.state_store,
        "is_processed_input",
        lambda source, external_id: True,
    )
    monkeypatch.setattr(
        inbox_processor.state_store,
        "get_processed_input",
        lambda source, external_id: {
            "status": "ready",
            "metadata": {"subject": "Cached", "summary": "already processed"},
        },
    )

    processed = inbox_processor.process_recent_inbox_messages(FakeService(), max_results=1)

    assert len(processed) == 1
    assert processed[0].skipped is True
    assert processed[0].status == "ready"
    assert processed[0].subject == "Cached"


def test_process_recent_inbox_messages_records_new_candidates(monkeypatch):
    monkeypatch.setattr(
        inbox_processor.gmail_adapter,
        "list_message_ids",
        lambda service, max_results=10, query="in:inbox": ["msg-2"],
    )
    monkeypatch.setattr(
        inbox_processor.gmail_adapter,
        "fetch_message",
        lambda service, message_id: type(
            "Msg",
            (),
            {
                "message_id": message_id,
                "subject": "Reminder",
                "sender": "clinic@example.com",
            },
        )(),
    )
    monkeypatch.setattr(
        inbox_processor.state_store,
        "init_db",
        lambda: None,
    )
    monkeypatch.setattr(
        inbox_processor.state_store,
        "is_processed_input",
        lambda source, external_id: False,
    )
    recorded = {}

    def _mark_processed(source, external_id, status, metadata):
        recorded["source"] = source
        recorded["external_id"] = external_id
        recorded["status"] = status
        recorded["metadata"] = metadata

    monkeypatch.setattr(
        inbox_processor.state_store,
        "mark_processed_input",
        _mark_processed,
    )
    monkeypatch.setattr(
        inbox_processor.assistant_workflow,
        "build_candidate_from_email",
        lambda message: type(
            "Candidate",
            (),
            {
                "status": "needs_clarification",
                "summary": "Reminder | missing calendar",
                "reason": "Email requires clarification before Molly can execute it.",
            },
        )(),
    )

    processed = inbox_processor.process_recent_inbox_messages(FakeService(), max_results=1)

    assert len(processed) == 1
    assert processed[0].status == "needs_clarification"
    assert processed[0].skipped is False
    assert recorded["source"] == "gmail"
    assert recorded["external_id"] == "msg-2"
    assert recorded["status"] == "needs_clarification"
