"""Central config, loaded from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

GRANTS_CACHE = DATA_DIR / "grants_cache.json"
LEDGER_FILE = DATA_DIR / "ledger.json"          # pre-accounts, kept for migration
LEDGERS_DIR = DATA_DIR / "ledgers"              # one file per account
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
DRAFTS_FILE = DATA_DIR / "drafts.json"

AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)

# Offline dev switch. Swaps BedrockModel for a rule-based stand-in so the
# plumbing can be run without model access. Never set this in deployment —
# see chest/agents/fake_model.py for what it does and does not prove.
CHEST_FAKE_MODEL = os.getenv("CHEST_FAKE_MODEL", "") not in ("", "0", "false")

CHEST_STORE = os.getenv("CHEST_STORE", "local")
DDB_LEDGER_TABLE = os.getenv("DDB_LEDGER_TABLE", "chest-ledger")

# Where the signup page is reachable. Local by default; set it to the ngrok
# https URL so the code the bot hands out points somewhere a phone can open.
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8000").rstrip("/")

CHEST_CHANNEL = os.getenv("CHEST_CHANNEL", "telegram")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

# iMessage via Blooio (https://blooio.com) — a third-party relay service, not
# an Apple-sanctioned API. Apple publishes no public API for sending iMessage;
# see the honesty note in README.md before treating this as "official."
BLOOIO_API_KEY = os.getenv("BLOOIO_API_KEY", "")
BLOOIO_WEBHOOK_SECRET = os.getenv("BLOOIO_WEBHOOK_SECRET", "")
BLOOIO_FROM_NUMBER = os.getenv("BLOOIO_FROM_NUMBER", "")


@dataclass(frozen=True)
class OrgProfile:
    """The nonprofit Chest is acting for. Used by the Eligibility Screener."""

    name: str
    ein: str
    applicant_type: str
    annual_budget: float
    state: str

    @classmethod
    def from_env(cls) -> "OrgProfile":
        return cls(
            name=os.getenv("ORG_NAME", "Riverside Neighborhood Heritage Museum"),
            ein=os.getenv("ORG_EIN", "00-0000000"),
            applicant_type=os.getenv(
                "ORG_TYPE",
                "Nonprofits having a 501(c)(3) status other than "
                "institutions of higher education",
            ),
            annual_budget=float(os.getenv("ORG_ANNUAL_BUDGET", "42000")),
            state=os.getenv("ORG_STATE", "IN"),
        )


ORG = OrgProfile.from_env()
ORG_MISSION_KEYWORDS = tuple(
    term.strip().lower()
    for term in os.getenv(
        "ORG_MISSION_KEYWORDS", "museum,local history,heritage preservation"
    ).split(",")
    if term.strip()
)
