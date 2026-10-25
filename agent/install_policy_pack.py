from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .policy_gate import PolicyGateError, load_selection, validate_policy_install


ROOT = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("FAILPROOFAI_HOME", Path.home() / ".failproofai"))
OPENCODE_CONFIG = Path.home() / ".config" / "opencode" / "opencode.json"


def install() -> None:
    selection = load_selection(ROOT / "policy-selection.json")
    source = f"{selection['pack_id']}@{selection['version']}"
    policies = ",".join(selection["policies"])
    env = os.environ.copy()
    env.pop("FAILPROOFAI_NO_DOWNLOAD", None)

    subprocess.run(
        [
            "failproofai",
            "policies",
            "add",
            source,
            "--cli",
            selection["cli"],
            "--policy",
            policies,
        ],
        check=True,
        env=env,
    )

    listing = subprocess.run(
        ["failproofai", "policies"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    validate_policy_install(
        HOME,
        selection,
        listing.stdout + "\n" + listing.stderr,
        OPENCODE_CONFIG,
    )


if __name__ == "__main__":
    try:
        install()
    except (PolicyGateError, KeyError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Riri policy-pack installation failed: {exc}") from exc
