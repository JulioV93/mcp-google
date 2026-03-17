from __future__ import annotations

from collections.abc import Sequence


def build_resource_identity(resource_type: str, **parts: object) -> dict[str, object]:
    payload: dict[str, object] = {"type": resource_type}
    for key, value in parts.items():
        if value is not None:
            payload[key] = value
    return payload


def enrich_resource(
    payload: dict[str, object],
    *,
    resource_type: str,
    human_summary: str,
    next_suggested_actions: list[str],
    safety_level: str,
    **identity_parts: object,
) -> dict[str, object]:
    result = dict(payload)
    result["resource_identity"] = build_resource_identity(resource_type, **identity_parts)
    result["human_summary"] = human_summary
    result["next_suggested_actions"] = next_suggested_actions
    result["safety_level"] = safety_level
    return result


def enrich_collection(
    *,
    items: Sequence[dict[str, object]],
    human_summary: str,
    next_suggested_actions: list[str],
    safety_level: str,
    resource_type: str,
    next_page_token: str | None = None,
    **identity_parts: object,
) -> dict[str, object]:
    result: dict[str, object] = {
        "items": list(items),
        "resource_identity": build_resource_identity(resource_type, **identity_parts),
        "human_summary": human_summary,
        "next_suggested_actions": next_suggested_actions,
        "safety_level": safety_level,
    }
    if next_page_token is not None:
        result["next_page_token"] = next_page_token
    return result
