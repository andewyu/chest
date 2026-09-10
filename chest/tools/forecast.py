"""Burn-rate forecast.

Deliberately simple: a linear projection over posted ledger entries. For a
hackathon this is the right amount of math — the interesting part of Chest is
what happens to the number, not how fancy the number is.

Outputs a Gap: how many dollars short, and the date it becomes real.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from chest.store.ledger import Entry, LedgerStore


@dataclass
class Gap:
    amount: float                 # dollars short at the horizon (0 if solvent)
    goes_negative_on: str | None  # ISO date the balance crosses zero
    current_balance: float
    monthly_net: float            # negative = burning
    horizon_days: int
    evidence: list[str]           # ledger citations backing the projection

    @property
    def is_real(self) -> bool:
        return self.amount > 0

    def summary(self) -> str:
        if not self.is_real:
            return (
                f"Balance ${self.current_balance:,.0f}, net "
                f"${self.monthly_net:+,.0f}/mo. No shortfall in the next "
                f"{self.horizon_days} days."
            )
        return (
            f"${self.amount:,.0f} short by {self.goes_negative_on}. "
            f"Balance ${self.current_balance:,.0f}, burning "
            f"${abs(self.monthly_net):,.0f}/mo."
        )


def forecast(
    store: LedgerStore,
    horizon_days: int = 365,
    lookback_days: int = 120,
    today: date | None = None,
) -> Gap:
    """Project one account's books forward. The store carries the account."""
    today = today or date.today()
    entries = store.posted()

    window_start = (today - timedelta(days=lookback_days)).isoformat()
    recent = [e for e in entries if e.occurred_on >= window_start]

    balance = sum(e.amount for e in entries if e.occurred_on <= today.isoformat())
    months = max(lookback_days / 30.0, 1.0)
    monthly_net = sum(e.amount for e in recent) / months

    # Recurring commitments already on the books get their own weight — a
    # volunteer treasurer's real problem is usually a known obligation, not noise.
    recurring = [e for e in entries if e.recurring]

    goes_negative_on = None
    gap = 0.0
    if monthly_net < 0:
        months_of_runway = balance / abs(monthly_net) if balance > 0 else 0.0
        days_of_runway = int(months_of_runway * 30)
        if days_of_runway <= horizon_days:
            goes_negative_on = (today + timedelta(days=days_of_runway)).isoformat()
            projected = balance + monthly_net * (horizon_days / 30.0)
            gap = abs(min(projected, 0.0))

    evidence = [e.cite() for e in sorted(recent, key=lambda x: x.amount)[:5]]
    evidence += [e.cite() for e in recurring[:3] if e.cite() not in evidence]

    return Gap(
        amount=round(gap, 2),
        goes_negative_on=goes_negative_on,
        current_balance=round(balance, 2),
        monthly_net=round(monthly_net, 2),
        horizon_days=horizon_days,
        evidence=evidence,
    )


def category_totals(entries: list[Entry]) -> dict[str, float]:
    """Used by the Drafter for budget-justification tables."""
    totals: dict[str, float] = {}
    for e in entries:
        totals[e.kind] = round(totals.get(e.kind, 0.0) + e.amount, 2)
    return totals
