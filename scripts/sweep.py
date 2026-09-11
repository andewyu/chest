"""The background sweep. No human triggers this.

EventBridge Scheduler invokes this on a cron. For every account with books, it
runs the forecast; only the ones with a real shortfall get the graph run, and
only those reach out to a human. That restraint is the product — an agent that
texts you every morning to say nothing happened is an agent you mute.

    python -m scripts.sweep --dry-run              # every account, print only
    python -m scripts.sweep --account acct_abc123  # just one
    python -m scripts.sweep                        # notify linked devices
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chest.store.accounts import Account, AccountStore  # noqa: E402
from chest.store.drafts import DraftStore  # noqa: E402
from chest.store.ledger import LedgerStore  # noqa: E402
from chest.tools.forecast import forecast  # noqa: E402


def _notify(identity_key: str, message: str) -> None:
    """Route a nudge back down whichever channel that identity came from."""
    from chest.channels.webhook import send_blooio, send_telegram

    channel, _, handle = identity_key.partition(":")
    if channel == "imessage":
        send_blooio(handle, message)
    elif channel == "telegram":
        send_telegram(handle, message)
    else:
        print(f"[{identity_key}] {message}")


def sweep_account(account: Account, accounts: AccountStore, notify: bool) -> dict:
    """Forecast one account; run the graph and reach out only if it's short."""
    gap = forecast(LedgerStore(account.id))
    if not gap.is_real:
        print(f"  {account.name}: quiet. {gap.summary()}")
        return {"account_id": account.id, "status": "quiet", "summary": gap.summary()}

    print(f"  {account.name}: {gap.summary()}")

    from chest.agents.graph import run_gap_to_grant

    try:
        message = run_gap_to_grant(
            account,
            gap.amount,
            gap.goes_negative_on or "unknown date",
        )
    except Exception as exc:
        # A model outage must not take down the whole scheduled run. The other
        # accounts still get swept, and this one is reported, not silent.
        print(f"  {account.name}: graph failed — {type(exc).__name__}: {exc}")
        return {"account_id": account.id, "status": "error", "error": str(exc)}

    targets = accounts.identities_for(account.id)
    if not notify or not targets:
        print(message)
        return {"account_id": account.id, "status": "drafted", "notified": 0}

    for identity in targets:
        if not message.startswith("BLOCKED:"):
            DraftStore().stage(f"{account.id}:{identity.key}", message)
        _notify(identity.key, message)
    return {"account_id": account.id, "status": "notified", "notified": len(targets)}


def run(account_id: str = "", notify: bool = True) -> list[dict]:
    accounts = AccountStore()
    targets = accounts.all()
    if account_id:
        targets = [a for a in targets if a.id == account_id]
        if not targets:
            print(f"no such account: {account_id}")
            return []

    print(f"sweeping {len(targets)} account(s)")
    return [sweep_account(a, accounts, notify) for a in targets]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="", help="sweep one account id")
    ap.add_argument("--dry-run", action="store_true", help="print, never send")
    args = ap.parse_args()
    run(account_id=args.account, notify=not args.dry_run)


def lambda_handler(event, context):  # AgentCore / Lambda entry point
    """One scheduled invocation sweeps every account."""
    results = run(account_id=(event or {}).get("account_id", ""), notify=True)
    return {
        "swept": len(results),
        "notified": sum(1 for r in results if r["status"] == "notified"),
        "errors": [r for r in results if r["status"] == "error"],
        "results": results,
    }


if __name__ == "__main__":
    main()
