from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .policy_gate import PolicyGateError, verify_policy_install


ROOT = Path(__file__).resolve().parent
HOME = Path(os.environ.get("FAILPROOFAI_HOME", Path.home() / ".failproofai"))
OPENCODE_URL = "http://127.0.0.1:4096"
POLICY_STATUS: dict[str, Any] | None = None
OPENCODE_PROCESS: subprocess.Popen[bytes] | None = None
SESSION_LOCKS: dict[str, asyncio.Lock] = {}
SESSION_LOCKS_GUARD = asyncio.Lock()


class AgentRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    session_id: str | None = None


def extract_text(parts: list[dict[str, Any]]) -> str:
    return "\n".join(
        part["text"]
        for part in parts
        if part.get("type") == "text" and isinstance(part.get("text"), str)
    ).strip()


def extract_policy_denials(parts: list[dict[str, Any]]) -> list[dict[str, str]]:
    denials: list[dict[str, str]] = []
    for part in parts:
        if part.get("type") != "tool":
            continue
        state = part.get("state")
        if not isinstance(state, dict):
            continue
        rendered = json.dumps(state, ensure_ascii=False, default=str).lower()
        has_policy_marker = "failproof" in rendered or "policy" in rendered
        has_denial_marker = any(
            marker in rendered for marker in ("denied", "blocked", "deny")
        )
        if has_policy_marker and has_denial_marker:
            reason = (
                "FailproofAI blocked a protected Git push"
                if any(marker in rendered for marker in ("force push", "--force", "git push"))
                else "FailproofAI denied this tool call"
            )
            denials.append(
                {
                    "tool": str(part.get("tool", "unknown")),
                    "reason": reason,
                }
            )
    return denials


async def _wait_for_opencode(process: subprocess.Popen[bytes]) -> None:
    async with httpx.AsyncClient(timeout=2) as client:
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError("OpenCode exited before its local API became ready")
            try:
                response = await client.get(f"{OPENCODE_URL}/global/health")
                response.raise_for_status()
                payload = response.json()
                if payload.get("healthy") is True:
                    return
            except (httpx.HTTPError, ValueError):
                await asyncio.sleep(1)
                continue
            await asyncio.sleep(1)
    raise RuntimeError("OpenCode's local API did not become ready within 60 seconds")


@asynccontextmanager
async def lifespan(_: FastAPI):
    global OPENCODE_PROCESS, POLICY_STATUS

    if os.environ.get("FAILPROOFAI_NO_DOWNLOAD") != "1":
        raise RuntimeError("FAILPROOFAI_NO_DOWNLOAD=1 is required at runtime")
    try:
        POLICY_STATUS = verify_policy_install(
            HOME,
            ROOT.parent / "policy-selection.json",
            Path.home() / ".config" / "opencode" / "opencode.json",
        )
    except PolicyGateError as exc:
        raise RuntimeError(
            f"Riri refuses to start because FailproofAI policies are not verified: {exc}"
        ) from exc

    env = os.environ.copy()
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "1"
    OPENCODE_PROCESS = subprocess.Popen(
        ["opencode", "serve", "--hostname", "127.0.0.1", "--port", "4096"],
        cwd="/workspace",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=None,
    )
    try:
        await _wait_for_opencode(OPENCODE_PROCESS)
        yield
    finally:
        if OPENCODE_PROCESS.poll() is None:
            OPENCODE_PROCESS.send_signal(signal.SIGTERM)
            try:
                OPENCODE_PROCESS.wait(timeout=10)
            except subprocess.TimeoutExpired:
                OPENCODE_PROCESS.kill()
                OPENCODE_PROCESS.wait(timeout=5)


app = FastAPI(title="Riri local agent", lifespan=lifespan)


@app.get("/ready")
async def ready() -> dict[str, Any]:
    if POLICY_STATUS is None:
        raise HTTPException(status_code=503, detail="FailproofAI policy status is unverified")
    return POLICY_STATUS


async def _session_lock(session_id: str) -> asyncio.Lock:
    async with SESSION_LOCKS_GUARD:
        return SESSION_LOCKS.setdefault(session_id, asyncio.Lock())


@app.post("/run")
async def run_agent(request: AgentRequest) -> dict[str, Any]:
    if POLICY_STATUS is None:
        raise HTTPException(status_code=503, detail="FailproofAI policy status is unverified")

    async with httpx.AsyncClient(base_url=OPENCODE_URL, timeout=600) as client:
        session_id = request.session_id
        try:
            if session_id is None:
                response = await client.post(
                    "/session",
                    json={"title": "Riri local coding session"},
                )
                response.raise_for_status()
                session_id = response.json()["id"]
            if not isinstance(session_id, str) or not session_id:
                raise ValueError("OpenCode returned an invalid session id")

            lock = await _session_lock(session_id)
            async with lock:
                response = await client.post(
                    f"/session/{session_id}/message",
                    json={
                        "agent": "riri",
                        "parts": [{"type": "text", "text": request.prompt}],
                    },
                )
                response.raise_for_status()
                result = response.json()
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise HTTPException(
                status_code=502,
                detail=f"The local coding agent failed to complete the request: {exc}",
            ) from exc

    raw_parts = result.get("parts")
    if not isinstance(raw_parts, list):
        raise HTTPException(
            status_code=502,
            detail="The local coding agent returned an invalid response",
        )
    parts = [part for part in raw_parts if isinstance(part, dict)]
    return {
        "session_id": session_id,
        "text": extract_text(parts),
        "policy_denials": extract_policy_denials(parts),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")
