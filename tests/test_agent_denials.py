from __future__ import annotations

import unittest

from agent.server import extract_policy_denials


class AgentDenialTests(unittest.TestCase):
    def test_converts_failproof_tool_error_to_a_policy_denial(self) -> None:
        parts = [
            {
                "type": "tool",
                "tool": "bash",
                "state": {
                    "status": "error",
                    "error": "FailproofAI policy denied git push --force",
                },
            }
        ]
        self.assertEqual(
            extract_policy_denials(parts),
            [{"tool": "bash", "reason": "FailproofAI blocked a protected Git push"}],
        )

    def test_does_not_label_unrelated_tool_errors_as_policy_denials(self) -> None:
        parts = [
            {
                "type": "tool",
                "tool": "bash",
                "state": {"status": "error", "error": "command not found"},
            }
        ]
        self.assertEqual(extract_policy_denials(parts), [])


if __name__ == "__main__":
    unittest.main()
