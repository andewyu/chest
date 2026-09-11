from chest.agents import treasurer
from chest.channels import webhook


def test_session_keys_are_stable_and_isolated():
    first = treasurer.session_key("telegram:123")

    assert first == treasurer.session_key("telegram:123")
    assert first != treasurer.session_key("telegram:456")
    assert "/" not in first
    assert ":" not in first


def test_webhook_builds_the_agent_for_the_callers_session(monkeypatch):
    seen: list[str] = []

    class FakeAgent:
        def __init__(self, session_id: str):
            self.session_id = session_id

        def __call__(self, text: str) -> str:
            return f"{self.session_id}:{text}"

    def fake_build_treasurer(session_id: str):
        seen.append(session_id)
        return FakeAgent(session_id)

    monkeypatch.setattr(webhook, "build_treasurer", fake_build_treasurer)

    assert webhook.handle("telegram:123", "balance") == "telegram:123:balance"
    assert webhook.handle("telegram:456", "balance") == "telegram:456:balance"
    assert seen == ["telegram:123", "telegram:456"]
