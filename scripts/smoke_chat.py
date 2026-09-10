"""Talk to the treasurer from the terminal, no ngrok and no phone.

    python scripts/smoke_chat.py                 # scripted log -> confirm -> post
    python scripts/smoke_chat.py --interactive   # type at it yourself
    python scripts/smoke_chat.py --sessions      # prove two orgs don't mix

Runs against a throwaway account in a temp directory, seeded with a sample
year of books, so a smoke run can never touch anyone's real ledger. Pair it
with CHEST_FAKE_MODEL=1 to exercise the plumbing without a model.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chest.store.ledger as ledger_module  # noqa: E402
from chest.agents.treasurer import for_session, reset_session  # noqa: E402
from chest.config import BEDROCK_MODEL_ID, CHEST_FAKE_MODEL  # noqa: E402
from chest.store.accounts import Account  # noqa: E402
from chest.store.ledger import LedgerStore  # noqa: E402

SCRIPT = [
    "hey",
    "paid 47 dollars for hoses",
    "yes",
    "whats the balance",
    "are we going to make it through the year",
]


def scratch_account(name: str) -> Account:
    """An account with its own seeded books, in a directory nobody else uses."""
    from scripts.seed_ledger import build

    account = Account(name=name)
    LedgerStore(account.id).bulk_post(build())
    return account


def say(session: str, account: Account, text: str) -> str:
    print(f"\n  \033[36mthem:\033[0m {text}")
    reply = str(for_session(session, account)(text)).strip()
    print(f"  \033[32mchest:\033[0m {reply}")
    return reply


def run_script(account: Account) -> None:
    for line in SCRIPT:
        say("smoke", account, line)


def run_interactive(account: Account) -> None:
    print("  (ctrl-c to quit)")
    while True:
        try:
            text = input("\n  them: ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if text:
            say("smoke", account, text)


def run_sessions() -> None:
    """Two orgs, one 'yes'. Only the thread that staged it should post."""
    garden = scratch_account("Riverside Garden Collective")
    shelter = scratch_account("Eastside Animal Shelter")
    print(f"\n  two accounts: {garden.name} and {shelter.name}")

    say("alice", garden, "paid 47 dollars for hoses")
    say("bob", shelter, "how much is in the account")
    print("\n  --- bob says yes; his org has nothing pending ---")
    say("bob", shelter, "yes")
    print("\n  --- alice says yes; hers posts ---")
    say("alice", garden, "yes")

    for label, account in (("garden", garden), ("shelter", shelter)):
        store = LedgerStore(account.id)
        hoses = [e for e in store.posted() if "hose" in e.memo.lower()]
        print(f"\n  {label}: {len(store.posted())} posted, "
              f"balance ${store.balance():,.2f}, hoses entries: {len(hoses)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interactive", action="store_true")
    ap.add_argument("--sessions", action="store_true")
    args = ap.parse_args()

    # Everything below writes here and nowhere else.
    ledger_module.LEDGERS_DIR = Path(tempfile.mkdtemp(prefix="chest-smoke-"))

    print(f"model: {BEDROCK_MODEL_ID}{'  (FAKE — plumbing only)' if CHEST_FAKE_MODEL else ''}")

    if args.sessions:
        run_sessions()
        return

    account = scratch_account("Riverside Community Garden Collective")
    store = LedgerStore(account.id)
    print(f"account: {account.name} ({account.id})")
    print(f"balance before: ${store.balance():,.2f}")
    try:
        run_interactive(account) if args.interactive else run_script(account)
        print(f"\nbalance after: ${store.balance():,.2f}")
    finally:
        reset_session("smoke")


if __name__ == "__main__":
    main()
