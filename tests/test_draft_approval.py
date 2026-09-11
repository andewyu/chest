from chest.channels import webhook
from chest.store.drafts import DraftStore


class FakeDrafts:
    def __init__(self):
        self.pending_sessions = {"chat-1"}
        self.approved = []
        self.edits = []

    def has_pending(self, session_id):
        return session_id in self.pending_sessions

    def approve(self, session_id):
        self.approved.append(session_id)

    def request_edit(self, session_id, instructions):
        self.edits.append((session_id, instructions))


def test_yes_approves_the_pending_grant_draft_without_calling_the_model(monkeypatch):
    drafts = FakeDrafts()
    monkeypatch.setattr(webhook, "DRAFTS", drafts)
    monkeypatch.setattr(
        webhook, "build_treasurer", lambda _: (_ for _ in ()).throw(AssertionError())
    )

    reply = webhook.handle("chat-1", "YES")

    assert drafts.approved == ["chat-1"]
    assert "did not submit" in reply


def test_edit_records_instructions_for_the_pending_draft(monkeypatch):
    drafts = FakeDrafts()
    monkeypatch.setattr(webhook, "DRAFTS", drafts)

    reply = webhook.handle("chat-1", "EDIT: make the opening shorter")

    assert drafts.edits == [("chat-1", "make the opening shorter")]
    assert "saved" in reply.lower()


def test_local_draft_state_hides_channel_id_and_is_owner_only(tmp_path):
    path = tmp_path / "drafts.json"
    drafts = DraftStore(path)

    drafts.stage("private-phone-number", "Reviewed draft")

    assert drafts.has_pending("private-phone-number")
    assert "private-phone-number" not in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600

    drafts.approve("private-phone-number")
    assert not drafts.has_pending("private-phone-number")
