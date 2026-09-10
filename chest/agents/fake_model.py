"""A stand-in model, for when Bedrock isn't available.

Set CHEST_FAKE_MODEL=1 and the treasurer runs without a single network call.
It exists so the plumbing can be exercised while model access is pending: the
tool wiring, the log -> confirm -> post state machine, per-session history, the
webhook routing, and the reply that comes back out the other end.

WHAT THIS DOES NOT TEST, and it is the important part: this is a lookup table
with delusions of intelligence. It matches a few regexes and calls the obvious
tool. It does not test whether the real model picks the right tool, extracts
the right amount, follows the voice, or gets the register right. A green run
here means the pipes are connected — nothing about how Chest sounds or thinks.
Only a real Bedrock call tells you that.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, AsyncIterable

from strands.models import Model

# "paid 47 dollars for hoses", "$47 on hoses", "got 120 in dues"
_AMOUNT = re.compile(r"\$?\s*(\d[\d,]*(?:\.\d{1,2})?)\s*(?:dollars|bucks|usd)?", re.I)
_INCOME = re.compile(r"\b(got|received|came in|deposit|donation|dues|grant|paid us)\b", re.I)
_SPEND = re.compile(r"\b(paid|spent|bought|cost|bill|invoice|for)\b", re.I)
_APPROVE = re.compile(r"^\s*(y|yes|yep|yeah|ok|okay|sure|confirm|approve|do it)\b", re.I)
_REJECT = re.compile(r"^\s*(n|no|nope|cancel|nevermind|never mind|discard)\b", re.I)
_BALANCE = re.compile(r"\b(balance|how much|what'?s in|account|broke|afford|runway|make it)\b", re.I)
_MEMO = re.compile(r"\b(?:for|on)\s+(.+?)\s*$", re.I)

_KINDS = {
    "dues": "dues",
    "donation": "donation",
    "donor": "donation",
    "grant": "grant",
}


def _text_of(message: dict) -> str:
    return " ".join(b["text"] for b in message.get("content", []) if "text" in b)


def _tool_results(messages: list[dict]) -> list[tuple[str, dict]]:
    """Every tool result so far, oldest first, as (tool_use_id, payload)."""
    out: list[tuple[str, dict]] = []
    tool_names: dict[str, str] = {}
    for message in messages:
        for block in message.get("content", []):
            if "toolUse" in block:
                tool_names[block["toolUse"]["toolUseId"]] = block["toolUse"]["name"]
            if "toolResult" in block:
                result = block["toolResult"]
                payload: dict = {}
                for item in result.get("content", []):
                    if "json" in item:
                        payload = item["json"]
                    elif "text" in item:
                        try:
                            payload = json.loads(item["text"])
                        except (ValueError, TypeError):
                            payload = {"text": item["text"]}
                payload = {**payload, "_tool": tool_names.get(result.get("toolUseId"), "")}
                out.append((result.get("toolUseId", ""), payload))
    return out


def _pending_id(messages: list[dict]) -> str:
    """The most recent entry this thread staged and hasn't posted."""
    staged = ""
    for _, payload in _tool_results(messages):
        if payload.get("_tool") == "log_transaction":
            staged = payload.get("id", "")
        elif payload.get("_tool") in {"confirm_transaction", "discard_transaction"}:
            staged = ""
    return staged


def _reply_to_tool_result(payload: dict) -> str:
    """The canned line for each tool. Deliberately plain — see the module note."""
    tool = payload.get("_tool")
    if tool == "log_transaction":
        return f"got it, {payload.get('readback', 'that')}. confirm?"
    if tool == "confirm_transaction":
        if not payload.get("ok"):
            return "nothing pending on my end to confirm."
        return f"posted. balance is {payload.get('balance_display', '?')}."
    if tool == "discard_transaction":
        return "dropped it."
    if tool == "current_balance":
        line = payload.get("balance_display", "?")
        if payload.get("shortfall"):
            return (
                f"{line}, running {payload.get('monthly_net_display', '')}. short by "
                f"{payload.get('short_by_display', '?')} around "
                f"{payload.get('runs_out_on', '?')}."
            )
        return f"{line}, running {payload.get('monthly_net_display', '')}."
    return "done."


def _decide(messages: list[dict]) -> tuple[str, dict] | str:
    """Return (tool_name, args) to call a tool, or a string to just talk."""
    results = _tool_results(messages)
    last = messages[-1] if messages else {}

    # Just came back from a tool? Say the line and stop.
    if last.get("role") == "user" and any("toolResult" in b for b in last.get("content", [])):
        return _reply_to_tool_result(results[-1][1])

    text = _text_of(last)

    if _APPROVE.match(text):
        entry_id = _pending_id(messages)
        if not entry_id:
            return "nothing pending in this thread."
        return ("confirm_transaction", {"entry_id": entry_id})

    if _REJECT.match(text):
        entry_id = _pending_id(messages)
        if not entry_id:
            return "nothing pending in this thread."
        return ("discard_transaction", {"entry_id": entry_id})

    money = _AMOUNT.search(text)
    if money and (_SPEND.search(text) or _INCOME.search(text)):
        amount = float(money.group(1).replace(",", ""))
        income = bool(_INCOME.search(text))
        kind = next((v for k, v in _KINDS.items() if k in text.lower()), None)
        if kind is None:
            kind = "other" if income else "expense"
        memo_match = _MEMO.search(text)
        memo = memo_match.group(1) if memo_match else text.strip()
        return (
            "log_transaction",
            {"amount": amount if income else -amount, "kind": kind, "memo": memo},
        )

    if _BALANCE.search(text):
        return ("current_balance", {})

    return "hey. what moved?"


class FakeModel(Model):
    """Implements just enough of the Strands Model interface to drive an Agent."""

    def __init__(self, model_id: str = "fake") -> None:
        self.config: dict[str, Any] = {"model_id": model_id}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError("FakeModel is for the conversational path only")

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterable[dict]:
        decision = _decide(list(messages))

        yield {"messageStart": {"role": "assistant"}}
        if isinstance(decision, str):
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": decision}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        else:
            name, args = decision
            yield {
                "contentBlockStart": {
                    "start": {
                        "toolUse": {"name": name, "toolUseId": f"tooluse_{uuid.uuid4().hex[:16]}"}
                    }
                }
            }
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(args)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
                "metrics": {"latencyMs": 0},
            }
        }
