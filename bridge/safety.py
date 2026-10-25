from __future__ import annotations

from typing import Any


PACK_ID = "FailproofAI/policies"
PACK_VERSION = "2.0.0"
PACK_CLI = "opencode"
REQUIRED_POLICIES = frozenset(
    {
        "sanitize-jwt",
        "sanitize-api-keys",
        "sanitize-connection-strings",
        "sanitize-private-key-content",
        "sanitize-bearer-tokens",
        "protect-env-vars",
        "block-env-files",
        "block-read-outside-cwd",
        "block-sudo",
        "block-curl-pipe-sh",
        "block-rm-rf",
        "block-secrets-write",
        "block-push-master",
        "block-force-push",
        "block-work-on-main",
    }
)


class PolicyGateError(RuntimeError):
    pass


def verify_prompt_gate(status: Any) -> None:
    if not isinstance(status, dict) or status.get("ready") is not True:
        raise PolicyGateError("The coding policy pack is not verified")
    if (
        status.get("pack_id") != PACK_ID
        or status.get("version") != PACK_VERSION
        or status.get("effect") != "enforce"
        or status.get("cli") != PACK_CLI
    ):
        raise PolicyGateError("The verified coding policy pack does not match Riri's pin")
    policies = status.get("policies")
    if not isinstance(policies, list) or not REQUIRED_POLICIES.issubset(policies):
        raise PolicyGateError("The verified coding policy pack is missing required policies")


def safe_alternative(denials: list[dict[str, str]]) -> str:
    context = " ".join(
        f"{item.get('tool', '')} {item.get('reason', '')}" for item in denials
    ).lower()
    if "force" in context or "push" in context:
        return (
            "Do not force-push or change the protected branch. Keep the work on a "
            "feature branch and prepare a pull request instead."
        )
    return (
        "Find a policy-compliant way to reach the same goal. Do not retry the "
        "denied action or bypass the policy; ask before any alternative with "
        "external side effects."
    )


def explain_denial(text: str, denials: list[dict[str, str]]) -> str:
    if not denials:
        return text
    explanation = (
        "Blocked by the installed FailproofAI policy. The denied action was not "
        "retried. A safer alternative is available below."
    )
    return f"{text.rstrip()}\n\n{explanation}".strip()
