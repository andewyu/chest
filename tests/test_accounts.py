"""Isolation is the promise, so it gets the most tests.

Chest tells every signup that their books are theirs. These are the assertions
behind that sentence: a ledger can only see its own account, an identity only
reaches the account it linked to, and an unlinked phone reaches nothing at all.
"""
from __future__ import annotations

import pytest

from chest.store.accounts import AccountStore
from chest.store.ledger import Entry, LedgerStore


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    monkeypatch.setattr("chest.store.ledger.LEDGERS_DIR", tmp_path / "ledgers")
    return AccountStore(path=tmp_path / "accounts.json")


@pytest.fixture
def two_orgs(accounts):
    garden = accounts.create("Riverside Garden", state="IN", annual_budget=42000)
    shelter = accounts.create("Eastside Shelter", state="OH", annual_budget=90000)
    LedgerStore(garden.id).bulk_post([
        Entry(amount=1000.0, kind="dues", memo="garden dues", occurred_on="2026-01-05"),
    ])
    LedgerStore(shelter.id).bulk_post([
        Entry(amount=250.0, kind="donation", memo="shelter gift", occurred_on="2026-01-06"),
    ])
    return garden, shelter


def test_a_ledger_needs_an_account():
    with pytest.raises(ValueError):
        LedgerStore("")


def test_ledgers_cannot_see_each_other(two_orgs):
    garden, shelter = two_orgs
    assert LedgerStore(garden.id).balance() == 1000.0
    assert LedgerStore(shelter.id).balance() == 250.0
    assert [e.memo for e in LedgerStore(garden.id).posted()] == ["garden dues"]


def test_an_entry_is_stamped_with_its_account(two_orgs):
    garden, _ = two_orgs
    store = LedgerStore(garden.id)
    entry = store.log(Entry(amount=-20.0, kind="expense", memo="soil", occurred_on="2026-02-01"))
    assert entry.account_id == garden.id


def test_one_orgs_entry_id_is_meaningless_to_another(two_orgs):
    """The obvious attack: paste someone else's entry id into your own thread."""
    garden, shelter = two_orgs
    staged = LedgerStore(garden.id).log(
        Entry(amount=-99.0, kind="expense", memo="hoses", occurred_on="2026-02-02")
    )
    assert LedgerStore(shelter.id).confirm(staged.id) is None
    assert LedgerStore(shelter.id).by_id(staged.id) is None
    # ...and the garden's entry is untouched by the attempt.
    assert LedgerStore(garden.id).by_id(staged.id).state == "pending"


def test_discard_from_another_account_leaves_the_entry_alone(two_orgs):
    garden, shelter = two_orgs
    staged = LedgerStore(garden.id).log(
        Entry(amount=-15.0, kind="expense", memo="twine", occurred_on="2026-02-03")
    )
    LedgerStore(shelter.id).discard(staged.id)
    assert LedgerStore(garden.id).by_id(staged.id) is not None


def test_identity_resolves_to_one_account(accounts, two_orgs):
    garden, shelter = two_orgs
    accounts.link("telegram:555", garden.id)
    accounts.link("telegram:777", shelter.id)
    assert accounts.account_for("telegram:555").id == garden.id
    assert accounts.account_for("telegram:777").id == shelter.id


def test_an_unknown_identity_has_no_account(accounts, two_orgs):
    assert accounts.account_for("telegram:999") is None


def test_relinking_moves_an_identity_and_leaves_no_second_binding(accounts, two_orgs):
    garden, shelter = two_orgs
    accounts.link("telegram:555", garden.id)
    accounts.link("telegram:555", shelter.id)
    assert accounts.account_for("telegram:555").id == shelter.id
    assert [i.key for i in accounts.identities_for(garden.id)] == []


def test_unlink_removes_access(accounts, two_orgs):
    garden, _ = two_orgs
    accounts.link("telegram:555", garden.id)
    assert accounts.unlink("telegram:555") is True
    assert accounts.account_for("telegram:555") is None


def test_codes_are_matched_case_and_punctuation_insensitively(accounts, two_orgs):
    garden, _ = two_orgs
    code = garden.link_code
    assert accounts.by_code(code.lower()).id == garden.id
    assert accounts.by_code(f" {code[:4]}-{code[4:]} ").id == garden.id
    assert accounts.by_code("") is None
    assert accounts.by_code("NOTACODE") is None


def test_codes_are_unique_across_a_crowd(accounts):
    codes = {accounts.create(f"Org {i}").link_code for i in range(50)}
    assert len(codes) == 50


def test_account_file_with_link_codes_is_owner_only(accounts):
    accounts.create("Private Org")

    assert accounts._path.stat().st_mode & 0o777 == 0o600


def test_rotating_a_code_invalidates_the_old_one(accounts, two_orgs):
    garden, _ = two_orgs
    old = garden.link_code
    rotated = accounts.rotate_code(garden.id)
    assert rotated.link_code != old
    assert accounts.by_code(old) is None
    assert accounts.by_code(rotated.link_code).id == garden.id


def test_the_agent_only_gets_tools_for_its_own_account(two_orgs, monkeypatch):
    """The isolation that matters most: what the model can reach."""
    from chest.agents import treasurer

    garden, shelter = two_orgs
    balance = next(t for t in treasurer._tools(garden) if t.tool_name == "current_balance")
    assert balance()["balance"] == 1000.0

    prompt = treasurer._role(shelter)
    assert "Eastside Shelter" in prompt and "Riverside Garden" not in prompt
