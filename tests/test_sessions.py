from chest.agents import treasurer
from chest.store.accounts import Account


def test_session_keys_are_stable_and_isolated():
    first = treasurer.session_key("telegram:123")

    assert first == treasurer.session_key("telegram:123")
    assert first != treasurer.session_key("telegram:456")
    assert "/" not in first
    assert ":" not in first


def test_account_is_part_of_the_persisted_session_key(monkeypatch):
    seen: list[str] = []

    class FakeManager:
        def __init__(self, session_id: str, **_kwargs):
            seen.append(session_id)

    monkeypatch.setattr(treasurer, "SnapshotSessionManager", FakeManager)
    monkeypatch.setattr(treasurer, "Agent", lambda **kwargs: kwargs)

    identity = "telegram:123"
    treasurer.for_session(identity, Account(name="One", id="acct_one"))
    treasurer.for_session(identity, Account(name="Two", id="acct_two"))

    assert seen == [
        treasurer.session_key("acct_one:telegram:123"),
        treasurer.session_key("acct_two:telegram:123"),
    ]


def test_session_directory_is_owner_only(tmp_path, monkeypatch):
    monkeypatch.setattr(treasurer, "SESSION_DIR", tmp_path / "sessions")
    monkeypatch.setattr(treasurer, "Agent", lambda **kwargs: kwargs)

    treasurer.for_session(
        "telegram:123", Account(name="Private Org", id="acct_private")
    )

    assert treasurer.SESSION_DIR.stat().st_mode & 0o777 == 0o700
