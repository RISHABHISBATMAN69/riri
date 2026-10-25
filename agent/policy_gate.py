from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


class PolicyGateError(RuntimeError):
    pass


def load_selection(selection_path: Path) -> dict[str, Any]:
    try:
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyGateError(f"Cannot read Riri's pinned policy selection: {exc}") from exc
    if not isinstance(selection, dict):
        raise PolicyGateError("Riri's pinned policy selection must be a JSON object")
    return selection


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyGateError(f"Cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise PolicyGateError(f"{label} must contain a JSON object")
    return value


def validate_policy_install(
    home: Path,
    selection: dict[str, Any],
    policies_output: str,
    opencode_config_path: Path,
) -> dict[str, Any]:
    pack_id = selection.get("pack_id")
    version = selection.get("version")
    cli = selection.get("cli")
    required = selection.get("policies")
    expected_hash = selection.get("artifact_sha256")
    if (
        not isinstance(pack_id, str)
        or not isinstance(version, str)
        or not isinstance(cli, str)
        or not isinstance(required, list)
        or not all(isinstance(name, str) for name in required)
        or not isinstance(expected_hash, str)
    ):
        raise PolicyGateError("Riri's pinned policy selection is incomplete")

    packs_dir = home / "policies" / "packs"
    installed = _read_json(packs_dir / "installed.json", "the installed pack manifest")
    records = installed.get("packs")
    if not isinstance(records, list):
        raise PolicyGateError("The installed pack manifest has no pack list")
    record = next(
        (
            item
            for item in records
            if isinstance(item, dict)
            and item.get("id") == pack_id
            and item.get("version") == version
        ),
        None,
    )
    if record is None:
        raise PolicyGateError(f"Required policy pack {pack_id}@{version} is not installed")
    if record.get("effect") != "enforce":
        raise PolicyGateError("The required coding policy pack is not in enforce mode")
    if record.get("clis") != [cli]:
        raise PolicyGateError(f"The required policy pack is not scoped only to {cli}")
    if record.get("source") is None or f"{pack_id}@{version}" not in str(record["source"]):
        raise PolicyGateError("The installed policy pack does not match its pinned release")
    enabled = record.get("enabled")
    if not isinstance(enabled, list) or not set(required).issubset(enabled):
        raise PolicyGateError("One or more required coding policies are not enabled")
    declared = record.get("policies")
    if not isinstance(declared, list):
        raise PolicyGateError("The installed policy pack has no declared policies")
    declared_names = {
        item.get("name")
        for item in declared
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if not set(required).issubset(declared_names):
        raise PolicyGateError("The installed policy pack is missing a required policy")

    entry = record.get("entry")
    if not isinstance(entry, str):
        raise PolicyGateError("The installed policy pack has no entry artifact")
    artifact = (packs_dir / entry).resolve()
    if not artifact.is_relative_to(packs_dir.resolve()) or not artifact.is_file():
        raise PolicyGateError("The installed policy pack entry artifact is missing")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if record.get("sha256") != expected_hash or digest != expected_hash:
        raise PolicyGateError("The installed policy pack failed its pinned SHA-256 check")

    config = _read_json(home / "policies-config.json", "the read-only policy configuration")
    configured = config.get("enabledPolicies")
    if not isinstance(configured, list) or not set(required).issubset(configured):
        raise PolicyGateError("The read-only policy configuration is missing required policies")

    pack_marker = f"{pack_id}@{version}"
    if not any(
        line.strip().lower().startswith("pack") and pack_marker.lower() in line.lower()
        for line in policies_output.splitlines()
    ):
        raise PolicyGateError(
            f"FailproofAI did not report {pack_marker} as a loaded policy pack"
        )

    agent_config = _read_json(opencode_config_path, "the OpenCode configuration")
    plugins = agent_config.get("plugin")
    if not isinstance(plugins, list) or not any(
        isinstance(plugin, str) and "failproofai" in plugin.lower()
        for plugin in plugins
    ):
        raise PolicyGateError("OpenCode is not wired to the FailproofAI hook")

    return {
        "ready": True,
        "pack_id": pack_id,
        "version": version,
        "effect": "enforce",
        "cli": cli,
        "policies": sorted(required),
    }


def verify_policy_install(
    home: Path,
    selection_path: Path,
    opencode_config_path: Path,
) -> dict[str, Any]:
    selection = load_selection(selection_path)
    env = {
        **os.environ,
        "FAILPROOFAI_NO_DOWNLOAD": "1",
    }
    try:
        result = subprocess.run(
            ["failproofai", "policies"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PolicyGateError(f"Could not verify FailproofAI policies: {exc}") from exc
    if result.returncode != 0:
        raise PolicyGateError(
            f"FailproofAI policy verification failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return validate_policy_install(
        home,
        selection,
        result.stdout + "\n" + result.stderr,
        opencode_config_path,
    )
