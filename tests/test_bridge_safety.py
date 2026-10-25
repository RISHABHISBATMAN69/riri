from __future__ import annotations

import unittest

from bridge.safety import (
    PACK_CLI,
    PACK_ID,
    PACK_VERSION,
    PolicyGateError,
    REQUIRED_POLICIES,
    explain_denial,
    safe_alternative,
    verify_prompt_gate,
)


class BridgeSafetyTests(unittest.TestCase):
    def test_accepts_only_the_pinned_enforcing_opencode_pack(self) -> None:
        verify_prompt_gate(
            {
                "ready": True,
                "pack_id": PACK_ID,
                "version": PACK_VERSION,
                "effect": "enforce",
                "cli": PACK_CLI,
                "policies": list(REQUIRED_POLICIES),
            }
        )

    def test_fails_closed_when_status_is_missing_or_mismatched(self) -> None:
        for status in (
            None,
            {"ready": False},
            {
                "ready": True,
                "pack_id": PACK_ID,
                "version": "9.9.9",
                "effect": "enforce",
                "cli": PACK_CLI,
                "policies": list(REQUIRED_POLICIES),
            },
        ):
            with self.subTest(status=status), self.assertRaises(PolicyGateError):
                verify_prompt_gate(status)

    def test_fails_closed_if_required_policy_is_missing(self) -> None:
        with self.assertRaisesRegex(PolicyGateError, "missing required"):
            verify_prompt_gate(
                {
                    "ready": True,
                    "pack_id": PACK_ID,
                    "version": PACK_VERSION,
                    "effect": "enforce",
                    "cli": PACK_CLI,
                    "policies": ["block-sudo"],
                }
            )

    def test_force_push_denial_offers_branch_and_pull_request(self) -> None:
        denials = [{"tool": "Bash", "reason": "force push denied"}]
        self.assertIn("feature branch", safe_alternative(denials))
        self.assertIn("Blocked by the installed", explain_denial("Stopped.", denials))

    def test_non_git_denial_offers_a_policy_compliant_alternative(self) -> None:
        alternative = safe_alternative([{"tool": "Write", "reason": "secrets write blocked"}])
        self.assertIn("policy-compliant", alternative)
        self.assertEqual(explain_denial("Allowed response.", []), "Allowed response.")


if __name__ == "__main__":
    unittest.main()
if __name__ == "__main__":
    unittest.main()
