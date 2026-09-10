"""The conversational front agent.

This is the thing the treasurer actually talks to. It handles logging
transactions with an explicit approval state machine (log -> confirm -> post),
answers balance questions, and can kick off the gap-to-grant sweep on demand.

The background sweep (EventBridge -> graph) is the same graph; this agent is
the interactive path into it.
"""
from __future__ import annotations

import re
from datetime import date

from strands import Agent, tool
from strands.models import BedrockModel

from chest.config import BEDROCK_MODEL_ID, ORG
from chest.store.ledger import Entry, LedgerStore
from chest.tools import forecast as fc

STORE = LedgerStore()


@tool
def log_transaction(amount: float, kind: str, memo: str, occurred_on: str = "") -> dict:
    """Stage a transaction as PENDING. It does not count until confirmed.

    amount: signed — income positive, expense negative.
    kind: dues | donation | grant | expense | other
    """
    entry = STORE.log(
        Entry(
            amount=float(amount),
            kind=kind,  # type: ignore[arg-type]
            memo=memo,
            occurred_on=occurred_on or date.today().isoformat(),
        )
    )
    return {"id": entry.id, "state": entry.state, "confirm_prompt": entry.cite()}


@tool
def confirm_transaction(entry_id: str) -> dict:
    """Post a pending transaction after the human confirms it."""
    entry = STORE.confirm(entry_id)
    if entry is None:
        return {"ok": False, "error": "no such pending entry"}
    return {"ok": True, "id": entry.id, "balance": STORE.balance()}


@tool
def discard_transaction(entry_id: str) -> dict:
    """Throw away a pending transaction the human rejected."""
    STORE.discard(entry_id)
    return {"ok": True}


@tool
def current_balance() -> dict:
    """What's in the chest right now, and the near-term outlook."""
    gap = fc.forecast()
    return {"balance": STORE.balance(), "outlook": gap.summary()}


TREASURER = Agent(
    model=BedrockModel(model_id=BEDROCK_MODEL_ID),
    name="treasurer",
    system_prompt=(
        f"You are Chest, the treasurer for {ORG.name}. You talk to a volunteer "
        "with a day job and no finance background, over a chat thread on their phone.\n\n"
        "Rules:\n"
        "- Keep every reply to one or two short lines. This is a text message, "
        "not a report.\n"
        "- When they mention money moving, call log_transaction, then read the "
        "entry back and ask them to confirm. Never post without confirmation.\n"
        "- 'yes' / 'yep' / 'y' confirms the most recent pending entry.\n"
        "- Never invent a number. If you don't have it in the ledger, say so.\n"
        "- You never submit a grant application. You draft; a human files.\n"
        "- No emoji unless they use one first."
    ),
    tools=[log_transaction, confirm_transaction, discard_transaction, current_balance],
)

_AFFIRM = re.compile(r"^\s*(y|yes|yep|yeah|ok|okay|confirm|approve)\b", re.I)
_EDIT = re.compile(r"^\s*edit\b", re.I)


def is_approval(text: str) -> bool:
    return bool(_AFFIRM.match(text))


def is_edit(text: str) -> bool:
    return bool(_EDIT.match(text))
