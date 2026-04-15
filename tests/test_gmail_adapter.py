import base64

import gmail_adapter


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def test_normalize_message_with_plain_text_payload():
    payload = {
        "id": "msg-1",
        "threadId": "thr-1",
        "snippet": "School concert this Friday",
        "internalDate": "1776211200000",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "School concert"},
                {"name": "From", "value": "teacher@example.com"},
            ],
            "mimeType": "text/plain",
            "body": {
                "data": _b64("YounHa concert this Friday at 18:00."),
            },
        },
    }

    message = gmail_adapter.normalize_message(payload)

    assert message.message_id == "msg-1"
    assert message.subject == "School concert"
    assert message.sender == "teacher@example.com"
    assert "YounHa concert" in message.body_text


def test_normalize_message_with_multipart_payload():
    payload = {
        "id": "msg-2",
        "threadId": "thr-2",
        "snippet": "Dentist reminder",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Reminder"},
                {"name": "From", "value": "clinic@example.com"},
            ],
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/html",
                    "body": {"data": _b64("<p>ignore html</p>")},
                },
                {
                    "mimeType": "text/plain",
                    "body": {"data": _b64("SungHwan dentist tomorrow 09:30.")},
                },
            ],
        },
    }

    message = gmail_adapter.normalize_message(payload)

    assert message.message_id == "msg-2"
    assert message.subject == "Reminder"
    assert "SungHwan dentist" in message.body_text
