from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException

os.environ.setdefault(
    "RIRI_DATABASE_PATH",
    str(Path(tempfile.gettempdir()) / f"riri-test-import-{os.getpid()}.sqlite3"),
)

from bridge import app as bridge_app
from bridge.audit import AuditLog


class PromptRouteTests(unittest.TestCase):
    def test_unverified_policy_pack_blocks_prompt_before_agent_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bridge_app.AUDIT = AuditLog(Path(directory) / "audit.sqlite3")
            prompt = "do-not-forward-this-private-prompt"

            async def submit() -> httpx.Response:
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=bridge_app.app),
                    base_url="http://riri.test",
                ) as client:
                    return await client.post(
                        "/api/chat",
                        json={
                            "conversation_id": "d41c8e9d-fc85-4d30-96b6-14af6eb4c06d",
                            "prompt": prompt,
                        },
                    )

            with patch(
                "bridge.app._get_policy_status",
                new=AsyncMock(
                    side_effect=HTTPException(
                        status_code=503,
                        detail="Nothing was sent to the agent.",
                    )
                ),
            ):
                response = asyncio.run(submit())

            self.assertEqual(response.status_code, 503)
            events = bridge_app.AUDIT.recent()
            event_types = [event["event_type"] for event in events]
            self.assertIn("prompt_received", event_types)
            self.assertIn("prompt_blocked", event_types)
            self.assertNotIn("agent_completed", event_types)
            self.assertNotIn(prompt, json.dumps(events))

    def test_non_coding_prompt_is_not_forwarded_to_agent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bridge_app.AUDIT = AuditLog(Path(directory) / "audit.sqlite3")
            prompt = "do-not-forward-this-general-question"

            async def submit() -> httpx.Response:
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=bridge_app.app),
                    base_url="http://riri.test",
                ) as client:
                    return await client.post(
                        "/api/chat",
                        json={
                            "conversation_id": "d41c8e9d-fc85-4d30-96b6-14af6eb4c06d",
                            "prompt": prompt,
                        },
                    )

            with (
                patch(
                    "bridge.app._get_policy_status",
                    new=AsyncMock(
                        return_value={
                            "pack_id": "FailproofAI/policies",
                            "version": "2.0.0",
                            "effect": "enforce",
                            "cli": "opencode",
                            "policies": ["block-force-push"],
                        }
                    ),
                ),
                patch(
                    "bridge.app._classify_coding_request",
                    new=AsyncMock(return_value=False),
                ),
            ):
                response = asyncio.run(submit())

            self.assertEqual(response.status_code, 422)
            events = bridge_app.AUDIT.recent()
            event_types = [event["event_type"] for event in events]
            self.assertIn("prompt_scope_blocked", event_types)
            self.assertNotIn("agent_completed", event_types)
            self.assertNotIn(prompt, json.dumps(events))


if __name__ == "__main__":
    unittest.main()
