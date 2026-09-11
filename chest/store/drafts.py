"""Small local state store for the human grant-draft approval boundary."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path

from chest.config import DRAFTS_FILE


class DraftStore:
    def __init__(self, path: Path = DRAFTS_FILE) -> None:
        self.path = path
        self._lock = threading.Lock()

    def stage(self, session_id: str, content: str) -> None:
        with self._lock:
            records = self._read()
            records[self._key(session_id)] = {
                "content": content,
                "status": "pending",
                "created_at": datetime.now(UTC).isoformat(),
            }
            self._write(records)

    def has_pending(self, session_id: str) -> bool:
        record = self._read().get(self._key(session_id), {})
        return record.get("status") == "pending"

    def approve(self, session_id: str) -> None:
        self._set_status(session_id, "approved")

    def request_edit(self, session_id: str, instructions: str) -> None:
        with self._lock:
            records = self._read()
            key = self._key(session_id)
            if key not in records or records[key].get("status") != "pending":
                raise ValueError("no pending draft")
            records[key]["status"] = "revision_requested"
            records[key]["revision_instructions"] = instructions
            self._write(records)

    def _set_status(self, session_id: str, status: str) -> None:
        with self._lock:
            records = self._read()
            key = self._key(session_id)
            if key not in records or records[key].get("status") != "pending":
                raise ValueError("no pending draft")
            records[key]["status"] = status
            self._write(records)

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text())

    def _write(self, records: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(json.dumps(records, indent=2))
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)

    @staticmethod
    def _key(session_id: str) -> str:
        return hashlib.sha256(session_id.encode("utf-8")).hexdigest()
