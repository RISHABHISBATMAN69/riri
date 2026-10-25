from __future__ import annotations

import json
from typing import Any


class ScopeCheckError(RuntimeError):
    pass


def parse_coding_classification(response: Any) -> bool:
    if not isinstance(response, dict):
        raise ScopeCheckError("The local coding-scope model returned an invalid response")
    message = response.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ScopeCheckError("The local coding-scope model returned no classification")
    try:
        classification = json.loads(message["content"])
    except json.JSONDecodeError as exc:
        raise ScopeCheckError(
            "The local coding-scope model returned malformed classification data"
        ) from exc
    if not isinstance(classification, dict) or not isinstance(
        classification.get("coding"), bool
    ):
        raise ScopeCheckError("The local coding-scope model returned an ambiguous classification")
    return classification["coding"]
