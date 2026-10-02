from __future__ import annotations

from typing import cast
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.base import Base
from app.google.gmail_client import build_raw_message
from app.schemas.gmail import (
    GmailConfirmSendEmailInput,
    GmailCreateDraftInput,
    GmailDeleteMessageInput,
    GmailGetMessageInput,
    GmailListMessagesInput,
    GmailRecipientMessageInput,
    GmailSendEmailInput,
)
from app.services.gmail_service import GmailService


def create_test_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", future=True, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    return session_factory()


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
    items = cast(list[dict[str, object]], result["items"])

    assert result["next_page_token"] == "next-msg"
    assert result["resource_identity"] == {"type": "gmail_message_collection"}
    assert items[0]["id"] == "msg-1"


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

    assert result["resource_identity"] == {
        "type": "gmail_message",
        "message_id": "msg-2",
        "thread_id": "thr-2",
    }
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
    message = cast(dict[str, object], result["message"])

    assert result["id"] == "draft-1"
    assert result["resource_identity"] == {
        "type": "gmail_draft",
        "draft_id": "draft-1",
        "message_id": "msg-3",
    }
    assert message["subject"] == "Draft subject"


def test_send_and_trash_message_return_expected_shape() -> None:
    session = create_test_session()
    service = GmailService(session, settings=Settings())
    service.client = Mock()
    service.client.send_message.return_value = {
        "id": "msg-sent",
        "threadId": "thr-sent",
        "labelIds": ["SENT"],
    }
    service.client.trash_message.return_value = {
        "id": "msg-sent",
        "threadId": "thr-sent",
        "labelIds": ["TRASH"],
    }

    send_payload = GmailSendEmailInput(
        message=GmailRecipientMessageInput(
            to=["user@example.com"],
            subject="Sent subject",
            body_text="Sent body",
        )
    )
    send_result = service.send_email(external_subject="user-1", input_data=send_payload)

    assert send_result["requires_confirmation"] is True
    operation_id = cast(str, send_result["operation_id"])

    confirm_result = service.confirm_send_email(
        external_subject="user-1",
        input_data=GmailConfirmSendEmailInput(operation_id=operation_id),
    )

    assert confirm_result["id"] == "msg-sent"
    assert confirm_result["thread_id"] == "thr-sent"
    assert confirm_result["safety_level"] == "destructive"
    assert confirm_result["confirmed"] is True

    delete_result = service.delete_message(
        external_subject="user-1",
        input_data=GmailDeleteMessageInput(message_id="msg-sent"),
    )
    assert delete_result == {
        "trashed": True,
        "message_id": "msg-sent",
        "thread_id": "thr-sent",
        "label_ids": ["TRASH"],
        "resource_identity": {
            "type": "gmail_message",
            "message_id": "msg-sent",
            "thread_id": "thr-sent",
        },
        "human_summary": "Moved Gmail message 'msg-sent' to trash.",
        "next_suggested_actions": ["gmail_list_messages", "gmail_list_threads"],
        "safety_level": "destructive",
    }
