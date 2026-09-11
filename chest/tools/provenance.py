"""Deterministic checks for ledger-grounded dollar figures in grant drafts."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Collection


_DOLLAR_FIGURE = re.compile(
    r"(?P<amount>\$(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)"
    r"(?:\s*\[(?P<citation>[A-Za-z0-9_-]+)\])?"
)


@dataclass(frozen=True)
class ProvenanceReport:
    valid: bool
    violations: list[str]


def validate_draft(draft: str, valid_entry_ids: Collection[str]) -> ProvenanceReport:
    """Require every dollar figure to cite an entry that exists in the ledger."""
    known = set(valid_entry_ids)
    violations: list[str] = []

    for match in _DOLLAR_FIGURE.finditer(draft):
        amount = match.group("amount")
        citation = match.group("citation")
        if citation is None:
            violations.append(f"{amount} has no ledger citation")
        elif citation not in known:
            violations.append(f"{amount} cites unknown ledger entry [{citation}]")

    return ProvenanceReport(valid=not violations, violations=violations)
