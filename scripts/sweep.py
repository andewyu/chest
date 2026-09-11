"""The background sweep. No human triggers this.

EventBridge Scheduler invokes this on a cron. It runs the graph, and only
reaches out to a human if there is an actual decision to make. That restraint
is the product.

    python -m scripts.sweep --chat-id <telegram chat id, or imessage phone number>
"""
from __future__ import annotations

import argparse

from chest.channels.webhook import send_blooio, send_telegram
from chest.config import CHEST_CHANNEL
from chest.store.drafts import DraftStore
from chest.tools.forecast import forecast


def _notify(chat_id: str, message: str) -> None:
    if CHEST_CHANNEL == "imessage":
        send_blooio(chat_id, message)
    else:
        send_telegram(chat_id, message)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat-id", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    gap = forecast()
    if not gap.is_real:
        print(f"No shortfall. Staying quiet. ({gap.summary()})")
        return

    from chest.agents.graph import run_gap_to_grant

    message = run_gap_to_grant(gap.amount, gap.goes_negative_on or "unknown date")
    if args.dry_run or not args.chat_id:
        print(message)
        return
    if not message.startswith("BLOCKED:"):
        DraftStore().stage(args.chat_id, message)
    _notify(args.chat_id, message)


def lambda_handler(event, context):  # AgentCore / Lambda entry point
    gap = forecast()
    if not gap.is_real:
        return {"status": "quiet", "summary": gap.summary()}
    from chest.agents.graph import run_gap_to_grant

    message = run_gap_to_grant(gap.amount, gap.goes_negative_on or "unknown date")
    chat_id = (event or {}).get("chat_id", "")
    if not chat_id:
        return {"status": "ready", "gap": gap.amount}
    if message.startswith("BLOCKED:"):
        _notify(chat_id, message)
        return {"status": "blocked", "gap": gap.amount}
    DraftStore().stage(chat_id, message)
    _notify(chat_id, message)
    return {"status": "notified", "gap": gap.amount}


if __name__ == "__main__":
    main()
