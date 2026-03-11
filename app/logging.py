from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping
from typing import Any, cast


REDACTED_KEYS = {
    "authorization",
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
        if isinstance(record.args, Mapping):
            record.args = cast(dict[str, Any], redact_value(record.args))
        if hasattr(record, "payload"):
            setattr(record, "payload", redact_value(getattr(record, "payload")))
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
            payload["payload"] = redact_value(getattr(record, "payload"))
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
