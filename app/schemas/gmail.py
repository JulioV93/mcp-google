from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class GmailRecipientMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: list[EmailStr] = Field(min_length=1)
    subject: str = Field(min_length=1)
    body_text: str = Field(min_length=1)
    cc: list[EmailStr] | None = None
    bcc: list[EmailStr] | None = None
    thread_id: str | None = None


class GmailListMessagesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    max_results: int = 20
    page_token: str | None = None


class GmailGetMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1)


class GmailListThreadsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    max_results: int = 20
    page_token: str | None = None


class GmailCreateDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: GmailRecipientMessageInput


class GmailUpdateDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str = Field(min_length=1)
    message: GmailRecipientMessageInput


class GmailDeleteDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str = Field(min_length=1)


class GmailSendEmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: GmailRecipientMessageInput


class GmailDeleteMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1)
