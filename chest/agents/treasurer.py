"""The conversational front agent.

This is the thing the treasurer actually talks to. It handles logging
transactions with an explicit approval state machine (log -> confirm -> post),
answers balance questions, and can kick off the gap-to-grant sweep on demand.

The background sweep (EventBridge -> graph) is the same graph; this agent is
the interactive path into it.

One agent per account, per channel identity. The tools are built inside
`_tools(account)` and close over that account's ledger, so a treasurer's tools
have no way to name another org's entries — the isolation is in what the tool
can reach, not in a rule the model is asked to follow. Conversation history is
per identity too, so "yes" always confirms *that* thread's pending entry.
"""
from __future__ import annotations

import hashlib
import re
import shutil
from datetime import date

from strands import Agent, tool
from strands.models import BedrockModel
from strands.session import SnapshotSessionManager
from strands.storage import LocalFileStorage

from chest.agents.voice import compose
from chest.config import BEDROCK_MODEL_ID, CHEST_FAKE_MODEL, DATA_DIR
from chest.store.accounts import Account
from chest.store.ledger import Entry, LedgerStore
from chest.tools import forecast as fc
SESSION_DIR = DATA_DIR / "sessions"

def _money(amount: float) -> str:
    """Format money once, here, so the model only ever copies a string.

    Handing a model a raw float and a rule about commas is a way to get
    "$9720.00" in a text thread. Handing it a finished string is not.
    """
    return f"${amount:,.2f}"


def _human_date(iso: str | None) -> str:
    """2027-01-31 -> "Jan 31, 2027". Nobody reads ISO dates out loud."""
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    year = "" if d.year == date.today().year else f", {d.year}"
    return f"{d.strftime('%b')} {d.day}{year}"


def _tools(account: Account) -> list:
    """This account's four tools, closed over this account's ledger."""
    store = LedgerStore(account.id)

    @tool
    def log_transaction(amount: float, kind: str, memo: str, occurred_on: str = "") -> dict:
        """Stage a transaction as PENDING. It does not count until confirmed.

        amount: signed — income positive, expense negative.
        kind: dues | donation | grant | expense | other
        """
        entry = store.log(
            Entry(
                amount=float(amount),
                kind=kind,  # type: ignore[arg-type]
                memo=memo,
                occurred_on=occurred_on or date.today().isoformat(),
            )
        )
        direction = "out" if entry.amount < 0 else "in"
        when = (
            ""
            if entry.occurred_on == date.today().isoformat()
            else f" on {_human_date(entry.occurred_on)}"
        )
        return {
            "id": entry.id,
            "state": entry.state,
            "amount_display": _money(abs(entry.amount)),
            "direction": direction,
            # Read this back verbatim. entry.cite() is the machine format — ISO
            # date and a minus sign — and the voice rules say neither of those
            # goes in front of a human. cite() stays for grant-draft provenance.
            "readback": f"{_money(abs(entry.amount))} {direction} for {entry.memo}{when}",
        }

    @tool
    def confirm_transaction(entry_id: str) -> dict:
        """Post a pending transaction after the human confirms it."""
        entry = store.confirm(entry_id)
        if entry is None:
            return {"ok": False, "error": "no such pending entry"}
        balance = store.balance()
        return {
            "ok": True,
            "id": entry.id,
            "balance": balance,
            "balance_display": _money(balance),
        }

    @tool
    def discard_transaction(entry_id: str) -> dict:
        """Throw away a pending transaction the human rejected."""
        store.discard(entry_id)
        return {"ok": True}

    @tool
    def current_balance() -> dict:
        """What's in the chest right now, and the near-term outlook.

        Fields don't overlap on purpose: gap.summary() restates the balance, and
        handing the model both gets you a reply that says the balance twice.
        """
        gap = fc.forecast(store)
        balance = store.balance()
        out = {
            "balance": balance,
            "balance_display": _money(balance),
            "monthly_net_display": f"{_money(abs(gap.monthly_net))}/mo "
            f"{'out' if gap.monthly_net < 0 else 'in'}",
            "shortfall": gap.is_real,
        }
        if gap.is_real:
            out["short_by_display"] = _money(gap.amount)
            out["runs_out_on"] = _human_date(gap.goes_negative_on)
        return out

    @tool
    def recent_entries(matching: str = "", kind: str = "", limit: int = 10) -> dict:
        """Look up posted entries.

        matching: search every posted entry's memo for this text. Use it
            whenever they name a thing — "summer program", "insurance", "dues".
            Without it you only get the newest few, which is NOT the whole
            ledger: never answer "we have no record of that" from an unfiltered
            list. Search first, then say it isn't there.
        kind: dues | donation | grant | expense | other
        limit: how many entries to return, newest first.
        """
        entries = [e for e in store.posted()]
        if matching.strip():
            needle = matching.strip().lower()
            entries = [e for e in entries if needle in e.memo.lower()]
        if kind.strip():
            entries = [e for e in entries if e.kind == kind.strip()]
        entries.sort(key=lambda e: e.occurred_on, reverse=True)

        shown = entries[: max(1, min(limit, 50))]
        # Total every match, not just the ones shown — a model asked "how much
        # did we spend on X" will otherwise add up the visible rows and be
        # confidently wrong.
        total = sum(e.amount for e in entries)
        return {
            "query": matching or kind or "most recent",
            "matches": len(entries),
            "showing": len(shown),
            "total_display": f"{_money(abs(total))} {'out' if total < 0 else 'in'}",
            "searched_whole_ledger": bool(matching.strip() or kind.strip()),
            "entries": [
                {
                    "id": e.id,
                    "date": _human_date(e.occurred_on),
                    "amount_display": _money(abs(e.amount)),
                    "direction": "out" if e.amount < 0 else "in",
                    "kind": e.kind,
                    "memo": e.memo,
                }
                for e in shown
            ],
        }

    return [
        log_transaction,
        confirm_transaction,
        discard_transaction,
        current_balance,
        recent_entries,
    ]


def _role(account: Account) -> str:
    return (
        f"You are Chest, the treasurer for {account.name}. You keep the books for "
        "a small volunteer-run nonprofit and you talk to one person: a volunteer "
        "with a day job and no finance background, over a text thread on their "
        "phone.\n\n"
        "WHAT YOU DO\n\n"
        "- Money moved? Call log_transaction, read the entry back in one line, ask "
        "them to confirm. Nothing posts before they say yes.\n"
        "- 'yes' / 'yep' / 'y' / 'ok' confirms the most recent pending entry in "
        "this thread. 'no' / 'nope' discards it.\n"
        "- Balance questions get the number and one line of context, nothing more.\n"
        "- 'what did we spend on X' means searching the books for X before you "
        "answer. Never tell them there's no record of something when all you "
        "did was glance at the newest few entries.\n"
        "- Totals come from the tool, not from you adding up rows.\n"
        "- If they're vague about an amount or what it was for, ask one short "
        "question. One. Don't interview them.\n\n"
        f"Everything you can reach is {account.name}'s books and nothing else. "
        "You have no way to see another organization's money, and you should "
        "never imply otherwise.\n\n"
        "Never name your own tools, fields, or files to them — no 'recent_entries', "
        "no 'the ledger file'. They don't know what those are and shouldn't have "
        "to. Say what you can and can't see in plain words: 'I've got everything "
        "back to March' or 'that's older than what I have'."
    )


def _model():
    if CHEST_FAKE_MODEL:
        from chest.agents.fake_model import FakeModel

        return FakeModel(model_id=BEDROCK_MODEL_ID)
    return BedrockModel(model_id=BEDROCK_MODEL_ID)


def _build(account: Account, session_id: str = "test") -> Agent:
    """Restore one account-scoped conversation for one channel identity."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_DIR.chmod(0o700)
    manager = SnapshotSessionManager(
        session_id=session_key(f"{account.id}:{session_id}"),
        storage=LocalFileStorage(str(SESSION_DIR)),
    )
    return Agent(
        model=_model(),
        agent_id="treasurer",
        name="treasurer",
        system_prompt=compose(_role(account)),
        tools=_tools(account),
        session_manager=manager,
    )


def for_session(session_id: str, account: Account) -> Agent:
    """Create an agent that restores only this account and identity's thread."""
    return _build(account, session_id)


def reset_session(session_id: str, account: Account) -> None:
    """Forget this identity's account-scoped history; leave the ledger alone."""
    key = session_key(f"{account.id}:{session_id}")
    shutil.rmtree(SESSION_DIR / key, ignore_errors=True)


def session_key(session_id: str) -> str:
    """Turn a channel identifier into an opaque, filesystem-safe session id."""
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32]


_AFFIRM = re.compile(r"^\s*(y|yes|yep|yeah|ok|okay|confirm|approve)\b", re.I)
_EDIT = re.compile(r"^\s*edit\b", re.I)


def is_approval(text: str) -> bool:
    return bool(_AFFIRM.match(text))


def is_edit(text: str) -> bool:
    return bool(_EDIT.match(text))
