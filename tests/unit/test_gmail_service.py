from __future__ import annotations

from unittest.mock import Mock

from app.google.gmail_client import build_raw_message
from app.schemas.gmail import (
    GmailCreateDraftInput,
    GmailDeleteMessageInput,
    GmailGetMessageInput,
    GmailListMessagesInput,
    GmailRecipientMessageInput,
    GmailSendEmailInput,
)
from app.services.gmail_service import GmailService


def test_build_raw_message_contains_thread_id_when_present() -> None:
    payload = build_raw_message(
        to=["user@example.com"],
        subject="Hello",
        body_text="Test body",
        thread_id="thread-123",
    )

    assert "raw" in payload
    assert payload["threadId"] == "thread-123"


def test_list_messages_normalizes_payload() -> None:
    session = Mock()
    service = GmailService(session)
    service.client = Mock()
    service.client.list_messages.return_value = {
        "messages": [{"id": "msg-1", "threadId": "thr-1"}],
        "nextPageToken": "next-msg",
    }

    result = service.list_messages(
        external_subject="user-1",
        input_data=GmailListMessagesInput(),
    )

    assert result["next_page_token"] == "next-msg"
    assert result["items"][0]["id"] == "msg-1"


def test_get_message_extracts_headers() -> None:
    session = Mock()
    service = GmailService(session)
    service.client = Mock()
    service.client.get_message.return_value = {
        "id": "msg-2",
        "threadId": "thr-2",
        "labelIds": ["INBOX"],
        "snippet": "Body preview",
        "internalDate": "1710000000000",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Status"},
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "user@example.com"},
            ]
        },
    }

    result = service.get_message(
        external_subject="user-1",
        input_data=GmailGetMessageInput(message_id="msg-2"),
    )

    assert result["subject"] == "Status"
    assert result["from"] == "sender@example.com"
    assert result["to"] == "user@example.com"


def test_create_draft_normalizes_response() -> None:
    session = Mock()
    service = GmailService(session)
    service.client = Mock()
    service.client.create_draft.return_value = {
        "id": "draft-1",
        "message": {
            "id": "msg-3",
            "threadId": "thr-3",
            "snippet": "Draft snippet",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Draft subject"},
                    {"name": "To", "value": "user@example.com"},
                ]
            },
        },
    }

    payload = GmailCreateDraftInput(
        message=GmailRecipientMessageInput(
            to=["user@example.com"],
            subject="Draft subject",
            body_text="Draft body",
        )
    )

    result = service.create_draft(external_subject="user-1", input_data=payload)

    assert result["id"] == "draft-1"
    assert result["message"]["subject"] == "Draft subject"


def test_send_and_delete_message_return_expected_shape() -> None:
    session = Mock()
    service = GmailService(session)
    service.client = Mock()
    service.client.send_message.return_value = {
        "id": "msg-sent",
        "threadId": "thr-sent",
        "labelIds": ["SENT"],
    }

    send_payload = GmailSendEmailInput(
        message=GmailRecipientMessageInput(
            to=["user@example.com"],
            subject="Sent subject",
            body_text="Sent body",
        )
    )
    send_result = service.send_email(external_subject="user-1", input_data=send_payload)

    assert send_result["id"] == "msg-sent"
    assert send_result["thread_id"] == "thr-sent"

    delete_result = service.delete_message(
        external_subject="user-1",
        input_data=GmailDeleteMessageInput(message_id="msg-sent"),
    )
    assert delete_result == {"deleted": True, "message_id": "msg-sent"}
