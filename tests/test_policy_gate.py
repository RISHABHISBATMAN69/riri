from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from agent.policy_gate import PolicyGateError, validate_policy_install


class PolicyGateTests(unittest.TestCase):
    def make_install(self, root: Path) -> tuple[Path, dict[str, object], Path, str]:
        home = root / "home"
        packs = home / "policies" / "packs"
        packs.mkdir(parents=True)
        artifact_bytes = b"verified test policy artifact"
        digest = hashlib.sha256(artifact_bytes).hexdigest()
        (packs / "artifacts").mkdir()
        (packs / "artifacts" / f"{digest}.mjs").write_bytes(artifact_bytes)
        required = ["block-force-push", "block-rm-rf"]
        selection: dict[str, object] = {
            "pack_id": "FailproofAI/policies",
            "version": "2.0.0",
            "artifact_sha256": digest,
            "cli": "opencode",
            "policies": required,
        }
        (packs / "installed.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "packs": [
                        {
                            "id": selection["pack_id"],
                            "version": selection["version"],
                            "source": "FailproofAI/policies@2.0.0",
                            "entry": f"artifacts/{digest}.mjs",
                            "sha256": digest,
                            "effect": "enforce",
                            "policies": [{"name": name} for name in required],
                            "enabled": required,
                            "clis": ["opencode"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (home / "policies-config.json").write_text(
            json.dumps({"enabledPolicies": required}),
            encoding="utf-8",
        )
        config = root / "opencode.json"
        config.write_text(json.dumps({"plugin": ["file:///usr/lib/failproofai/plugin.mjs"]}))
        output = "Pack — FailproofAI/policies@2.0.0\n"
        return home, selection, output, config

    def test_accepts_loaded_enforcing_pack_scoped_to_opencode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.make_install(Path(directory))
            status = validate_policy_install(*fixture)
        self.assertTrue(status["ready"])
        self.assertEqual(status["cli"], "opencode")

    def test_rejects_missing_or_unloaded_pack(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home, selection, config, _ = self.make_install(Path(directory))
            with self.assertRaisesRegex(PolicyGateError, "loaded policy pack"):
                validate_policy_install(home, selection, "", config)

    def test_rejects_wrong_agent_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home, selection, config, output = self.make_install(Path(directory))
            manifest_path = home / "policies" / "packs" / "installed.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["packs"][0]["clis"] = ["claude"]
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(PolicyGateError, "scoped only to opencode"):
                validate_policy_install(home, selection, output, config)

    def test_rejects_disabled_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home, selection, config, output = self.make_install(Path(directory))
            manifest_path = home / "policies" / "packs" / "installed.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["packs"][0]["enabled"] = ["block-force-push"]
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(PolicyGateError, "not enabled"):
                validate_policy_install(home, selection, output, config)

    def test_rejects_artifact_checksum_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home, selection, config, output = self.make_install(Path(directory))
            artifact = next((home / "policies" / "packs" / "artifacts").glob("*.mjs"))
            artifact.write_bytes(b"changed policy artifact")
            with self.assertRaisesRegex(PolicyGateError, "SHA-256"):
                validate_policy_install(home, selection, output, config)


if __name__ == "__main__":
    unittest.main()
