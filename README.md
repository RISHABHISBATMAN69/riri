# Riri

Riri is a local chat UI and bridge to an OpenCode coding agent running against
Ollama. A small local model classifies whether a request is about coding; a
separate coding model runs the agent. FailproofAI's installed coding policy pack
evaluates the agent's tool calls; Riri does not edit or replace those policies.

The bridge checks policy readiness before **every** prompt. If the expected pack
is missing, corrupt, out of date, scoped to another agent, or not loaded by the
FailproofAI CLI, the prompt is not forwarded. OpenCode's prompt hook is not used
as a substitute for this check.

## Requirements

- Docker Engine and Docker Compose
- 16 GB RAM minimum; 32 GB is recommended for larger models
- Internet access during the first image/model setup to retrieve the pinned
  FailproofAI release, container images, npm packages, and Ollama model weights
- About 50 GB of free disk space is recommended

Inference and agent tools run locally. The OpenCode agent container is attached
only to an internal Docker network and has no internet route. The Ollama
container has a separate network for downloading its model on first start; it
serves inference locally and does not call a hosted model API. The UI is
published only on `127.0.0.1`.

## Start Riri

```sh
RIRI_UID="$(id -u)" RIRI_GID="$(id -g)" docker compose up --build
```

The UID/GID values let the non-root agent write the mounted workspace and its
local state. If omitted, the image uses `10001` for both.

Open [http://127.0.0.1:8080](http://127.0.0.1:8080). The first start downloads
two Ollama models and can take several minutes: `qwen2.5:3b` for coding-scope
classification and `qwen2.5-coder:7b` for the agent.

To use a different project directory, set `RIRI_WORKSPACE` before starting:

```sh
RIRI_WORKSPACE=/absolute/path/to/project docker compose up --build
```

To change the local UI port, set `RIRI_PORT`.

The policy selection and the OpenCode hook are installed during the agent image
build. The selection pins `FailproofAI/policies@2.0.0`, verifies the release
asset with FailproofAI's `SHA256SUMS` validation, checks the installed artifact
against its pinned SHA-256, and scopes it to `opencode`. At runtime,
`FAILPROOFAI_NO_DOWNLOAD=1` prevents policy downloads. The policy configuration
is mounted read-only; the installed policy artifact is kept in the immutable
agent image.

## What the safeguards cover

- **Prompt path:** the bridge queries the agent's verified policy status before
  forwarding each prompt, then uses the small local model to reject requests
  outside the coding-agent scope. A failed check returns an error and records
  that the prompt was blocked; it never falls back to forwarding. The intake
  classifier is a scope filter, not a security policy.
- **Tool path:** OpenCode is wired to FailproofAI's supported OpenCode hook. The
  pinned pack is scoped to OpenCode and enables coding policies including
  force-push, main-branch, destructive-command, environment-file, and secret
  protections. FailproofAI remains the authority for tool-call decisions.
- **Denials:** Riri reports detected policy denials and offers a policy-safe
  alternative. It does not automatically retry a denied action; the user must
  choose the alternative, which is evaluated again by FailproofAI.
- **Audit:** a local SQLite database records request lifecycle, scope checks,
  and policy
  outcomes without storing prompt or response text.

These layers reduce risk but do not make an agent literally failproof. The model
may still make mistakes, and this starter stack is not a substitute for backups,
review, or a trusted host.

## Policy pack updates

The pack version and entry-artifact SHA-256 are recorded in
`agent/policy-selection.json`. To update the pack, review the publisher's new
release and checksum, change both values, rebuild the agent image, and verify
the matching policy names and OpenCode scope. Do not edit policy code or
`installed.json` by hand. The release checksum is integrity verification, not a
cryptographic publisher signature.

## Local verification

```sh
python3 -m unittest discover -s tests
python3 -m compileall -q agent bridge tests
```

Docker is required to run the full stack. Container build and runtime behavior
cannot be exercised by the unit tests alone.
