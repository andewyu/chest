"""Amazon Bedrock AgentCore Runtime entry point for Chest.

Run locally with ``python -m chest.agentcore_app``. AgentCore Runtime supplies
POST /invocations and GET /ping around this entry point when deployed.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from chest.channels.webhook import handle

app = BedrockAgentCoreApp()


def invoke_payload(
    payload: dict[str, Any] | None,
    *,
    handler: Callable[[str, str], str] = handle,
    sweep_handler: Callable[[str], str] | None = None,
    fallback_session_id: str | None = None,
) -> dict[str, str]:
    """Validate an AgentCore invocation and route it to an isolated session."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    session_id = payload.get("session_id") or fallback_session_id
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id is required")

    if payload.get("action") == "sweep" or payload.get("prompt") == "/sweep":
        reply = (sweep_handler or _run_sweep)(session_id)
        return {"message": reply, "session_id": session_id}

    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    if len(prompt) > 4000:
        raise ValueError("prompt is too long")

    reply = handler(f"agentcore:{session_id}", prompt)
    return {"message": reply, "session_id": session_id}


def _run_sweep(session_id: str) -> str:
    from chest.agents.graph import run_gap_to_grant
    from chest.store.drafts import DraftStore
    from chest.tools.forecast import forecast

    gap = forecast()
    if not gap.is_real:
        return f"No shortfall. Staying quiet. ({gap.summary()})"
    message = run_gap_to_grant(gap.amount, gap.goes_negative_on or "unknown date")
    if not message.startswith("BLOCKED:"):
        DraftStore().stage(session_id, message)
    return message


@app.entrypoint
def chest_agent(payload: dict[str, Any], context: Any) -> dict[str, str]:
    """AgentCore handler; its runtime session id keeps callers separated."""
    runtime_session_id = getattr(context, "session_id", None)
    return invoke_payload(payload, fallback_session_id=runtime_session_id)


if __name__ == "__main__":
    app.run()
