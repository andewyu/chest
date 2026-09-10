"""Move the pre-accounts ledger into an account. Run once, safely repeatable.

Before accounts, Chest kept one ledger at data/ledger.json for the org named
in .env. This lifts that into a real account so the demo data survives, and
leaves the old file alone.

    python -m scripts.migrate_accounts
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chest.config import LEDGER_FILE, ORG  # noqa: E402
from chest.store.accounts import AccountStore  # noqa: E402
from chest.store.ledger import Entry, LedgerStore  # noqa: E402


def main() -> int:
    accounts = AccountStore()

    existing = next((a for a in accounts.all() if a.name == ORG.name), None)
    if existing is not None:
        print(f"{ORG.name} already has an account: {existing.id}")
        print(f"link code: {existing.link_code}")
        return 0

    account = accounts.create(
        ORG.name,
        ein=ORG.ein,
        applicant_type=ORG.applicant_type,
        annual_budget=ORG.annual_budget,
        state=ORG.state,
    )
    print(f"created {account.id} for {account.name}")

    if LEDGER_FILE.exists():
        raw = json.loads(LEDGER_FILE.read_text())
        store = LedgerStore(account.id)
        entries = []
        for e in raw:
            e.pop("account_id", None)
            entries.append(Entry(account_id=account.id, **e))
        store._replace_all(entries)
        print(f"imported {len(entries)} entries from {LEDGER_FILE.name}")
        print(f"balance: ${store.balance():,.2f}")
        print(f"(the old file is left in place; delete it when you're happy)")

    print(f"\nlink code: {account.link_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
