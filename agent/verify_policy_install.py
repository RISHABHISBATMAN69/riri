import os
from pathlib import Path

from .policy_gate import PolicyGateError, verify_policy_install


try:
    status = verify_policy_install(
        Path(os.environ.get("FAILPROOFAI_HOME", Path.home() / ".failproofai")),
        Path(__file__).resolve().parent.parent / "policy-selection.json",
        Path.home() / ".config" / "opencode" / "opencode.json",
    )
except PolicyGateError as exc:
    raise SystemExit(f"Riri will not start without verified FailproofAI policies: {exc}") from exc

print(
    f"Verified {status['pack_id']}@{status['version']} "
    f"for {status['cli']} ({len(status['policies'])} policies, enforce)"
)
