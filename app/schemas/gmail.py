from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class GmailRecipientMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: list[EmailStr] = Field(min_length=1, description="Primary email recipients.")
    subject: str = Field(min_length=1, description="Email subject line.")
    body_text: str = Field(min_length=1, description="Plain-text email body.")
    cc: list[EmailStr] | None = Field(default=None, description="Optional CC recipients.")
    bcc: list[EmailStr] | None = Field(default=None, description="Optional BCC recipients.")
    thread_id: str | None = Field(
        default=None, description="Optional Gmail thread ID for conversation continuity."
    )


class GmailListMessagesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    max_results: int = Field(default=20, ge=1, le=500)
    page_token: str | None = None


class GmailGetMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1, description="Gmail message ID.")


class GmailListThreadsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    max_results: int = Field(default=20, ge=1, le=500)
    page_token: str | None = None


class GmailCreateDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: GmailRecipientMessageInput


class GmailUpdateDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str = Field(min_length=1, description="Gmail draft ID.")
    message: GmailRecipientMessageInput


class GmailDeleteDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str = Field(min_length=1, description="Gmail draft ID.")


class GmailSendEmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: GmailRecipientMessageInput


class GmailConfirmSendEmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(min_length=1, description="Prepared Gmail send operation ID.")


class GmailDeleteMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1, description="Gmail message ID to move to trash.")
