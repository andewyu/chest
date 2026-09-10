"""The voice is a product decision, so it gets a test.

These don't assert on model output — that costs money and isn't deterministic.
They assert on the two things that silently break the voice without breaking
anything else: an agent that stops being composed with it, and a tool that
hands the model a string a human was never meant to read.
"""
from __future__ import annotations

from datetime import date

import pytest

from chest.agents import graph, treasurer
from chest.store.accounts import Account
from chest.agents.voice import EXAMPLES, MONEY_RULES, REGISTER, STYLE, compose


ACCOUNT = Account(name="Test Collective", id="acct_test")


@pytest.fixture
def scratch_ledger(tmp_path, monkeypatch):
    """Anything that calls a @tool writes to a real ledger unless you move it.

    LedgerStore resolves its path from the module-level LEDGERS_DIR on every
    call, so patching that is enough — and it keeps the test off the books of
    every account at once.
    """
    monkeypatch.setattr("chest.store.ledger.LEDGERS_DIR", tmp_path)
    return tmp_path


def _tool(name: str):
    """One of the treasurer's account-bound tools, by name."""
    return next(t for t in treasurer._tools(ACCOUNT) if t.tool_name == name)


def test_compose_includes_every_section():
    prompt = compose("You are a test agent.")
    assert prompt.startswith("You are a test agent.")
    for section in (STYLE, REGISTER, MONEY_RULES, EXAMPLES):
        assert section in prompt


def test_human_facing_agents_speak_in_the_voice():
    """The treasurer and the reviewer are the only two a human reads."""
    agents = graph.build_agents(ACCOUNT)
    for agent in (treasurer._build(ACCOUNT), agents["reviewer"]):
        assert MONEY_RULES in agent.system_prompt
        assert REGISTER in agent.system_prompt


def test_upstream_graph_agents_stay_clinical():
    """Composing the voice into these would waste tokens on nobody."""
    agents = graph.build_agents(ACCOUNT)
    for name in ("forecaster", "scout", "screener", "drafter"):
        assert STYLE not in agents[name].system_prompt


def test_readback_is_shaped_for_a_human(scratch_ledger):
    result = _tool("log_transaction")(amount=-47.0, kind="expense", memo="hoses")

    assert result["readback"] == "$47.00 out for hoses"
    assert "-" not in result["readback"]  # direction is a word, not a sign
    assert date.today().isoformat() not in result["readback"]  # no ISO dates


def test_readback_says_the_date_only_when_it_isn_t_today(scratch_ledger):
    result = _tool("log_transaction")(
        amount=120.0, kind="dues", memo="dues", occurred_on="2026-03-14"
    )
    assert result["readback"] == "$120.00 in for dues on Mar 14"


def test_money_never_loses_its_comma():
    assert treasurer._money(9720.5) == "$9,720.50"
