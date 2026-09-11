import pytest

from chest import agentcore_app
from chest.agentcore_app import invoke_payload
from chest.store.accounts import Account


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


def test_unlinked_agentcore_session_cannot_sweep_an_account(monkeypatch):
    class Accounts:
        def account_for(self, _identity):
            return None

    monkeypatch.setattr("chest.store.accounts.AccountStore", Accounts)

    assert "link" in agentcore_app._run_sweep("new-session").lower()


def test_agentcore_sweep_uses_linked_accounts_books(monkeypatch):
    account = Account(name="Test Org", id="acct_test")
    seen: dict[str, str] = {}

    class Accounts:
        def account_for(self, identity):
            seen["identity"] = identity
            return account

    class Gap:
        is_real = True
        amount = 1200.0
        goes_negative_on = "2026-12-01"

    class Drafts:
        def stage(self, owner, content):
            seen["owner"] = owner
            seen["content"] = content

    monkeypatch.setattr("chest.store.accounts.AccountStore", Accounts)
    monkeypatch.setattr("chest.store.ledger.LedgerStore", lambda account_id: account_id)
    monkeypatch.setattr("chest.tools.forecast.forecast", lambda store: Gap())
    monkeypatch.setattr("chest.store.drafts.DraftStore", Drafts)
    monkeypatch.setattr(
        "chest.agents.graph.run_gap_to_grant",
        lambda linked, amount, date: f"draft:{linked.id}:{amount}:{date}",
    )

    result = agentcore_app._run_sweep("demo-user")

    assert result == "draft:acct_test:1200.0:2026-12-01"
    assert seen["identity"] == "agentcore:demo-user"
    assert seen["owner"] == "acct_test:agentcore:demo-user"
