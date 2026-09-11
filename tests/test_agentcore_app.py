import pytest

from chest.agentcore_app import invoke_payload


def test_agentcore_payload_routes_prompt_and_session():
    calls = []

    result = invoke_payload(
        {"prompt": "What is our balance?", "session_id": "demo-user"},
        handler=lambda session_id, text: calls.append((session_id, text)) or "Balance ready",
    )

    assert calls == [("agentcore:demo-user", "What is our balance?")]
    assert result == {"message": "Balance ready", "session_id": "demo-user"}


def test_agentcore_payload_can_run_the_gap_to_grant_workflow():
    calls = []

    result = invoke_payload(
        {"action": "sweep", "session_id": "demo-user"},
        handler=lambda *_: "unused",
        sweep_handler=lambda session_id: calls.append(session_id) or "Reviewed draft",
    )

    assert calls == ["demo-user"]
    assert result == {"message": "Reviewed draft", "session_id": "demo-user"}


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"prompt": ""}, {"prompt": "x" * 4001}, {"prompt": "ok", "session_id": ""}],
)
def test_agentcore_payload_rejects_invalid_input(payload):
    with pytest.raises(ValueError):
        invoke_payload(payload, handler=lambda *_: "unused")
