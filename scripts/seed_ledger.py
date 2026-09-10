"""Seed a believable small-nonprofit ledger that produces a real shortfall.

A community garden collective: modest dues income, a summer program that costs
more than dues cover, and an insurance renewal that lands in the fall. The
forecast should surface a gap in the low five figures — which is exactly the
band where real federal opportunities live.

    python -m scripts.seed_ledger
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from chest.store.ledger import Entry, LedgerStore

random.seed(7)


def build(today: date | None = None) -> list[Entry]:
    today = today or date.today()
    entries: list[Entry] = []

    def add(days_ago: int, amount: float, kind: str, memo: str, recurring=False):
        entries.append(
            Entry(
                amount=amount,
                kind=kind,  # type: ignore[arg-type]
                memo=memo,
                occurred_on=(today - timedelta(days=days_ago)).isoformat(),
                state="posted",
                recurring=recurring,
            )
        )

    # Opening position
    add(200, 18400.00, "other", "Opening balance carried from prior year")

    # Monthly dues — 34 members at $15, drifting down as the year goes on
    for m in range(7, 0, -1):
        members = 34 - (7 - m)
        add(m * 30, members * 15.0, "dues", f"Monthly member dues ({members} members)", recurring=True)

    # Two donations
    add(120, 2500.00, "donation", "Spring fundraiser — Hensley family gift")
    add(58, 750.00, "donation", "Neighborhood association contribution")

    # Recurring costs
    for m in range(7, 0, -1):
        add(m * 30 - 3, -410.00, "expense", "Water utility — main plot irrigation", recurring=True)
        add(m * 30 - 5, -265.00, "expense", "Tool shed rent", recurring=True)

    # Summer program — the thing that breaks the budget
    add(95, -3200.00, "expense", "Youth summer program — seeds, soil, raised beds")
    add(88, -1875.00, "expense", "Youth summer program — stipends for 3 teen leads")
    add(61, -2400.00, "expense", "Youth summer program — second session materials")

    # The obligation on the horizon
    add(20, -1980.00, "expense", "General liability insurance — annual renewal", recurring=True)
    add(12, -640.00, "expense", "Soil remediation testing (city requirement)")
    add(5, -318.00, "expense", "Replacement hoses and hand tools")

    return entries


def main() -> None:
    store = LedgerStore()
    entries = build()
    store._replace_all(entries)  # local dev only
    from chest.tools.forecast import forecast

    gap = forecast()
    print(f"Seeded {len(entries)} entries.")
    print(gap.summary())
    for line in gap.evidence:
        print("  " + line)


if __name__ == "__main__":
    main()
