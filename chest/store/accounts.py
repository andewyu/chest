"""Accounts: one per nonprofit, and the identities that can text it.

Chest went from "the org in .env" to "whoever signed up". That means two
lookups the rest of the app leans on:

    account_id -> the org profile (name, EIN, applicant type, budget, state)
    channel identity -> account_id      ("telegram:12345" -> "acct_ab12cd34")

Everything money-shaped is keyed by account_id from here down. A ledger is
opened as LedgerStore(account_id) and can only see that account's entries, so
isolation is a property of the storage layout rather than a filter somebody
has to remember to apply.

Linking is a code, not a password: you sign up on the web, get an 8-character
code, and text it to the bot. The code proves "the person holding this signed
up for this org" — good enough for a shared volunteer thread, and deliberately
reusable so a treasurer can hand it to the rest of the board. Rotate it with
AccountStore.rotate_code if it leaks; anyone who has it can read the books.
"""
from __future__ import annotations

import json
import os
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from chest.config import ACCOUNTS_FILE

# No 0/O/1/I/L — these get read off a screen and typed into a phone.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def _new_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(8))


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Account:
    """One nonprofit's books, and the profile the grant agents reason about."""

    name: str
    ein: str = "00-0000000"
    applicant_type: str = (
        "Nonprofits having a 501(c)(3) status other than "
        "institutions of higher education"
    )
    annual_budget: float = 50000.0
    state: str = "IN"
    id: str = field(default_factory=lambda: f"acct_{uuid.uuid4().hex[:12]}")
    link_code: str = field(default_factory=_new_code)
    created_at: str = field(default_factory=_now)

    def profile(self):
        """The shape the agents already expect (chest.config.OrgProfile)."""
        from chest.config import OrgProfile

        return OrgProfile(
            name=self.name,
            ein=self.ein,
            applicant_type=self.applicant_type,
            annual_budget=self.annual_budget,
            state=self.state,
        )


@dataclass
class Identity:
    """One channel handle bound to one account. The join table, basically."""

    key: str          # "telegram:12345", "imessage:+15551234567"
    account_id: str
    linked_at: str = field(default_factory=_now)


class AccountStore:
    """Local JSON today. Same interface the DynamoDB backend will need."""

    def __init__(self, path=None) -> None:
        self._path = path or ACCOUNTS_FILE

    # ---------- persistence ----------

    def _read(self) -> dict:
        if not self._path.exists():
            return {"accounts": [], "identities": []}
        return json.loads(self._path.read_text())

    def _write(self, data: dict) -> None:
        """Write via a temp file and os.replace.

        The web server and the bot are two processes sharing this file. A torn
        write would take the demo down; os.replace is atomic, so a reader sees
        either the old file or the new one. It does not make read-modify-write
        safe — two simultaneous signups can still lose one — which is a real
        limitation of a JSON backend and the reason the DynamoDB path exists.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, self._path)

    # ---------- accounts ----------

    def create(self, name: str, **profile) -> Account:
        account = Account(name=name, **profile)
        data = self._read()
        data["accounts"].append(asdict(account))
        self._write(data)
        return account

    def all(self) -> list[Account]:
        return [Account(**a) for a in self._read()["accounts"]]

    def get(self, account_id: str) -> Account | None:
        return next((a for a in self.all() if a.id == account_id), None)

    def by_code(self, code: str) -> Account | None:
        """Codes are typed by humans, so normalize before comparing."""
        wanted = (code or "").strip().upper().replace("-", "").replace(" ", "")
        if not wanted:
            return None
        return next((a for a in self.all() if a.link_code == wanted), None)

    def rotate_code(self, account_id: str) -> Account | None:
        data = self._read()
        for raw in data["accounts"]:
            if raw["id"] == account_id:
                raw["link_code"] = _new_code()
                self._write(data)
                return Account(**raw)
        return None

    # ---------- identities ----------

    def link(self, key: str, account_id: str) -> Identity:
        """Bind a channel handle to an account, replacing any earlier binding.

        Re-linking is allowed on purpose: one phone may keep books for two orgs
        in different seasons, and the newest code wins.
        """
        identity = Identity(key=key, account_id=account_id)
        data = self._read()
        data["identities"] = [i for i in data["identities"] if i["key"] != key]
        data["identities"].append(asdict(identity))
        self._write(data)
        return identity

    def unlink(self, key: str) -> bool:
        data = self._read()
        before = len(data["identities"])
        data["identities"] = [i for i in data["identities"] if i["key"] != key]
        self._write(data)
        return len(data["identities"]) < before

    def account_for(self, key: str) -> Account | None:
        """The account this channel handle speaks for, or None if unlinked."""
        identity = next((i for i in self._read()["identities"] if i["key"] == key), None)
        return self.get(identity["account_id"]) if identity else None

    def identities_for(self, account_id: str) -> list[Identity]:
        return [
            Identity(**i)
            for i in self._read()["identities"]
            if i["account_id"] == account_id
        ]
