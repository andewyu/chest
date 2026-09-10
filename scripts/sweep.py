"""The background sweep. No human triggers this.

EventBridge Scheduler invokes this on a cron. It runs the graph, and only
reaches out to a human if there is an actual decision to make. That restraint
is the product.

    python -m scripts.sweep --chat-id <telegram chat id>
"""
from __future__ import annotations

import argparse

from chest.channels.webhook import send_telegram
from chest.tools.forecast import forecast


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat-id", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    gap = forecast()
    if not gap.is_real:
        print(f"No shortfall. Staying quiet. ({gap.summary()})")
        return

    from chest.agents.graph import get_graph

    graph = get_graph()
    result = graph(
        f"The org is projected ${gap.amount:,.0f} short by {gap.goes_negative_on}. "
        f"Find and draft the grant that closes it."
    )

    message = str(result)
    if args.dry_run or not args.chat_id:
        print(message)
        return
    send_telegram(args.chat_id, message)


def lambda_handler(event, context):  # AgentCore / Lambda entry point
    gap = forecast()
    if not gap.is_real:
        return {"status": "quiet", "summary": gap.summary()}
    from chest.agents.graph import get_graph

    result = get_graph()(
        f"The org is projected ${gap.amount:,.0f} short by {gap.goes_negative_on}. "
        f"Find and draft the grant that closes it."
    )
    chat_id = (event or {}).get("chat_id", "")
    if chat_id:
        send_telegram(chat_id, str(result))
    return {"status": "notified", "gap": gap.amount}


if __name__ == "__main__":
    main()
