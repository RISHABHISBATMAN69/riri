from __future__ import annotations

import unittest

from bridge.scope import ScopeCheckError, parse_coding_classification


class ScopeClassificationTests(unittest.TestCase):
    def test_accepts_explicit_coding_classification(self) -> None:
        self.assertTrue(parse_coding_classification({"message": {"content": '{"coding":true}'}}))

    def test_rejects_non_coding_classification(self) -> None:
        self.assertFalse(
            parse_coding_classification({"message": {"content": '{"coding":false}'}})
        )

    def test_fails_closed_on_malformed_or_ambiguous_response(self) -> None:
        for response in (
            {},
            {"message": {"content": "yes"}},
            {"message": {"content": '{"coding":"yes"}'}},
        ):
            with self.subTest(response=response), self.assertRaises(ScopeCheckError):
                parse_coding_classification(response)


if __name__ == "__main__":
    unittest.main()
