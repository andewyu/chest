"""Ledger store.

Local JSON in dev, DynamoDB in deployment. Same interface either way, so the
agents never know which one they're talking to.

Every entry carries a stable `id` — that id is what makes provenance possible:
a figure in a grant draft cites the ledger entries it came from.

Every store is opened for exactly one account: LedgerStore(account_id). Local
entries live in their own file per account, so one org physically cannot read
another's books — isolation is the storage layout, not a WHERE clause someone
has to remember. The DynamoDB backend keeps the same promise by filtering on
the partition key.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Iterable, Literal

try:  # only needed for the DynamoDB backend
    from boto3.dynamodb.conditions import Key
except ImportError:  # pragma: no cover
    Key = None  # type: ignore[assignment]

from chest.config import CHEST_STORE, DDB_LEDGER_TABLE, LEDGERS_DIR

EntryKind = Literal["dues", "donation", "grant", "expense", "other"]
EntryState = Literal["pending", "posted"]


@dataclass
class Entry:
    """One ledger line. Amounts are signed: income positive, expense negative."""

    amount: float
    kind: EntryKind
    memo: str
    occurred_on: str  # ISO date
    account_id: str = ""
    state: EntryState = "pending"
    recurring: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    logged_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def cite(self) -> str:
        sign = "+" if self.amount >= 0 else "-"
        return f"[{self.id}] {self.occurred_on} {sign}${abs(self.amount):,.2f} {self.memo}"


class LedgerStore:
    """Append-only-ish ledger with an explicit log → confirm → post state machine."""

    def __init__(self, account_id: str) -> None:
        if not account_id:
            raise ValueError("a ledger belongs to an account; pass an account_id")
        self.account_id = account_id
        self._backend = CHEST_STORE
        self._table = None
        if self._backend == "dynamodb":
            import boto3

            self._table = boto3.resource("dynamodb").Table(DDB_LEDGER_TABLE)

    @property
    def path(self):
        """This account's ledger file. Local backend only."""
        return LEDGERS_DIR / f"{self.account_id}.json"

    # ---------- reads ----------

    def all(self) -> list[Entry]:
        if self._backend == "dynamodb":
            items = self._table.query(
                KeyConditionExpression=Key("account_id").eq(self.account_id)
            ).get("Items", [])
            return [Entry(**{k: _coerce(k, v) for k, v in i.items()}) for i in items]
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text())
        # The account_id filter is belt-and-braces: the file is already scoped.
        return [Entry(**e) for e in raw if e.get("account_id", self.account_id) == self.account_id]

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
        entry.account_id = self.account_id
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
        entry = self.by_id(entry_id)
        if entry is None or entry.state != "pending":
            return False
        if self._backend == "dynamodb":
            self._table.delete_item(
                Key={"account_id": self.account_id, "id": entry_id}
            )
            return True
        entries = [e for e in self.all() if e.id != entry_id]
        self._replace_all(entries)
        return True

    def bulk_post(self, entries: Iterable[Entry]) -> None:
        for e in entries:
            e.account_id = self.account_id
            e.state = "posted"
            self._upsert(e)

    # ---------- backend plumbing ----------

    def _upsert(self, entry: Entry) -> None:
        entry.account_id = self.account_id
        if self._backend == "dynamodb":
            self._table.put_item(Item=_to_dynamodb(asdict(entry)))
            return
        entries = [e for e in self.all() if e.id != entry.id]
        entries.append(entry)
        self._replace_all(entries)

    def _replace_all(self, entries: list[Entry]) -> None:
        if self._backend == "dynamodb":
            raise NotImplementedError("bulk replace is a local-dev convenience only")
        # The file belongs to this account, so everything written into it does
        # too — otherwise an entry built elsewhere lands with a blank owner and
        # reads back as invisible.
        for e in entries:
            e.account_id = self.account_id
        entries.sort(key=lambda e: e.occurred_on)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic: a half-written ledger is worse than a stale one, and the web
        # server and the bot both write here.
        tmp = self.path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps([asdict(e) for e in entries], indent=2))
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)


def _coerce(key: str, value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _to_dynamodb(value):
    """Convert Python floats recursively because DynamoDB rejects them."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _to_dynamodb(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_dynamodb(item) for item in value]
    return value
