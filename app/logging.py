from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Mapping
from typing import Any, cast
from uuid import uuid4

REDACTED_KEYS = {
    "authorization",
    "code",
    "state",
    "code_verifier",
    "token_encryption_key",
    "access_token",
    "refresh_token",
    "token",
    "client_secret",
    "jwt_shared_secret",
    "body_text",
    "subject",
    "description",
    "notes",
    "raw",
    "content_text",
    "content_base64",
    "content_markdown",
    "values",
    "to",
    "cc",
    "bcc",
}


def redact_value(value: object) -> object:
    if isinstance(value, Mapping):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            if key.lower() in REDACTED_KEYS:
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_value(item)
        return redacted
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Third-party tracebacks can retain an earlier provider exception and its secrets.
        record.exc_info = None
        record.exc_text = None
        if isinstance(record.args, Mapping):
            record.args = cast(dict[str, Any], redact_value(record.args))
        if hasattr(record, "payload"):
            record.payload = redact_value(record.payload)
        message = record.getMessage()
        record.msg = re.sub(
            r"(?i)([?&](?:code|state|access_token|refresh_token|token|client_secret)=)[^&\s]+",
            r"\1[redacted]",
            message,
        )
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "payload"):
            payload["payload"] = redact_value(record.payload)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(level: str, *, json_logs: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RedactionFilter())
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


AUDIT_ARGUMENT_KEYS = frozenset(
    {
        "operation_id",
        "file_id",
        "event_id",
        "calendar_id",
        "task_id",
        "tasklist_id",
        "message_id",
        "thread_id",
        "draft_id",
        "permission_id",
        "parent_id",
        "target_file_id",
        "add_parent_id",
        "remove_parent_id",
        "page_size",
        "max_results",
        "content_size",
        "size_bytes",
        "mode",
        "permanent",
        "include_trashed",
        "show_completed",
        "show_hidden",
        "previous_profile",
        "access_profile",
    }
)


def audit_arguments(arguments: object) -> dict[str, object]:
    if not isinstance(arguments, Mapping):
        return {}
    return {
        key: value
        for key, value in arguments.items()
        if key in AUDIT_ARGUMENT_KEYS and isinstance(value, (str, int, float, bool, type(None)))
    }


_PROVIDER_REASONS = frozenset(
    {
        "dailylimitexceeded",
        "quotaexceeded",
        "ratelimitexceeded",
        "userratelimitexceeded",
        "autherror",
        "forbidden",
        "forbiddenfornonorganizer",
        "insufficientpermissions",
        "notfound",
        "conflict",
        "duplicate",
        "conditionnotmet",
        "backenderror",
        "other",
    }
)


def record_operation_failure(session, error: Exception) -> str:
    """Record only server-controlled classifications, never exception messages or bodies."""
    from app.errors import AppError

    diagnostic_id = session.info.setdefault("diagnostic_id", uuid4().hex)
    payload = {
        "diagnostic_id": diagnostic_id,
        "tool": session.info.get("diagnostic_tool", "google_operation"),
        "stage": session.info.get("diagnostic_stage", "provider_request"),
        "exception_type": type(error).__name__,
    }
    if isinstance(error, AppError):
        payload["error_code"] = error.code
        metadata = error.metadata or {}
        status = metadata.get("provider_status_code")
        if type(status) is int and 100 <= status <= 599:
            payload["provider_status_code"] = status
        reason = metadata.get("provider_reason")
        if isinstance(reason, str):
            payload["provider_reason"] = reason if reason.lower() in _PROVIDER_REASONS else "other"
    # Text logging also retains the safe payload; no configuration change is required.
    logging.getLogger("app.google.diagnostics").warning(
        "Google operation failure %s",
        json.dumps(payload, ensure_ascii=True),
        extra={"payload": payload},
    )
    return diagnostic_id
