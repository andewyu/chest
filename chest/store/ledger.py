"""Ledger store.

Local JSON in dev, DynamoDB in deployment. Same interface either way, so the
agents never know which one they're talking to.

Every entry carries a stable `id` — that id is what makes provenance possible:
a figure in a grant draft cites the ledger entries it came from.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Iterable, Literal

from chest.config import CHEST_STORE, DDB_LEDGER_TABLE, LEDGER_FILE

EntryKind = Literal["dues", "donation", "grant", "expense", "other"]
EntryState = Literal["pending", "posted"]


@dataclass
class Entry:
    """One ledger line. Amounts are signed: income positive, expense negative."""

    amount: float
    kind: EntryKind
    memo: str
    occurred_on: str  # ISO date
    state: EntryState = "pending"
    recurring: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    logged_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def cite(self) -> str:
        sign = "+" if self.amount >= 0 else "-"
        return f"[{self.id}] {self.occurred_on} {sign}${abs(self.amount):,.2f} {self.memo}"


class LedgerStore:
    """Append-only-ish ledger with an explicit log → confirm → post state machine."""

    def __init__(self) -> None:
        self._backend = CHEST_STORE
        self._table = None
        if self._backend == "dynamodb":
            import boto3

            self._table = boto3.resource("dynamodb").Table(DDB_LEDGER_TABLE)

    # ---------- reads ----------

    def all(self) -> list[Entry]:
        if self._backend == "dynamodb":
            items = self._table.scan().get("Items", [])
            return [Entry(**{k: _coerce(k, v) for k, v in i.items()}) for i in items]
        if not LEDGER_FILE.exists():
            return []
        raw = json.loads(LEDGER_FILE.read_text())
        return [Entry(**e) for e in raw]

    def posted(self) -> list[Entry]:
        return [e for e in self.all() if e.state == "posted"]

    def balance(self, as_of: date | None = None) -> float:
        cutoff = (as_of or date.today()).isoformat()
        return sum(e.amount for e in self.posted() if e.occurred_on <= cutoff)

    def by_id(self, entry_id: str) -> Entry | None:
        return next((e for e in self.all() if e.id == entry_id), None)

    # ---------- writes ----------

    def log(self, entry: Entry) -> Entry:
        """Stage an entry as `pending`. Nothing counts until it is confirmed."""
        entry.state = "pending"
        self._upsert(entry)
        return entry

    def confirm(self, entry_id: str) -> Entry | None:
        """The human said yes. Post it."""
        entry = self.by_id(entry_id)
        if entry is None:
            return None
        entry.state = "posted"
        self._upsert(entry)
        return entry

    def discard(self, entry_id: str) -> bool:
        entries = [e for e in self.all() if e.id != entry_id]
        self._replace_all(entries)
        return True

    def bulk_post(self, entries: Iterable[Entry]) -> None:
        for e in entries:
            e.state = "posted"
            self._upsert(e)

    # ---------- backend plumbing ----------

    def _upsert(self, entry: Entry) -> None:
        if self._backend == "dynamodb":
            self._table.put_item(Item=asdict(entry))
            return
        entries = [e for e in self.all() if e.id != entry.id]
        entries.append(entry)
        self._replace_all(entries)

    def _replace_all(self, entries: list[Entry]) -> None:
        if self._backend == "dynamodb":
            raise NotImplementedError("bulk replace is a local-dev convenience only")
        entries.sort(key=lambda e: e.occurred_on)
        LEDGER_FILE.write_text(json.dumps([asdict(e) for e in entries], indent=2))


def _coerce(key: str, value):
    from decimal import Decimal

    if isinstance(value, Decimal):
        return float(value)
    return value
