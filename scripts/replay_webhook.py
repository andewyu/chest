"""Prove the whole inbound path works, without ngrok, a phone, or a real message.

    CHEST_FAKE_MODEL=1 python scripts/replay_webhook.py

Every channel Chest speaks is a provider POSTing JSON at an endpoint, and every
account starts as a form submission. So this drives the real thing end to end
in-process: sign up two organizations over HTTP, link a phone to each with the
code the web page handed out, then POST exactly what Telegram, Twilio and
Blooio post — same payload shapes, same headers — and check what comes back.

It runs against a throwaway accounts file and ledger directory, and outbound
sends are captured instead of delivered, so nothing leaves the machine and no
real books are touched.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from twilio.request_validator import RequestValidator  # noqa: E402

import chest.store.ledger as ledger_module  # noqa: E402
from chest.channels import webhook  # noqa: E402
from chest.store.accounts import AccountStore  # noqa: E402

SENT: list[tuple[str, str]] = []
PASSED = 0
FAILED = 0


def _sandbox() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="chest-replay-"))
    ledger_module.LEDGERS_DIR = tmp / "ledgers"
    webhook.ACCOUNTS = AccountStore(path=tmp / "accounts.json")
    webhook.TELEGRAM_WEBHOOK_SECRET = "replay-telegram-secret"
    webhook.TWILIO_AUTH_TOKEN = "replay-twilio-token"
    webhook.BLOOIO_WEBHOOK_SECRET = "replay-blooio-secret"
    webhook.send_telegram = lambda chat_id, text: SENT.append((f"telegram:{chat_id}", text))
    webhook.send_blooio = lambda chat_id, text: SENT.append((f"imessage:{chat_id}", text))


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  PASS  {label}" + (f"  -> {detail}" if detail else ""))
    else:
        FAILED += 1
        print(f"  FAIL  {label}" + (f"  -> {detail}" if detail else ""))


def telegram_update(chat_id: int, text: str) -> dict:
    """The shape Telegram actually POSTs to a bot webhook."""
    return {
        "update_id": 100,
        "message": {
            "message_id": 1,
            "from": {"id": chat_id, "is_bot": False, "first_name": "Vol"},
            "chat": {"id": chat_id, "type": "private"},
            "date": 1757520000,
            "text": text,
        },
    }


def post_telegram(client: TestClient, chat_id: int, text: str):
    return client.post(
        "/telegram",
        json=telegram_update(chat_id, text),
        headers={
            "X-Telegram-Bot-Api-Secret-Token": webhook.TELEGRAM_WEBHOOK_SECRET
        },
    )


def blooio_event(from_number: str, text: str) -> dict:
    return {"event": "message.received", "data": {"from": from_number, "text": text}}


def sign_up(client: TestClient, name: str, seed: bool = True) -> tuple[str, str]:
    """Sign up over HTTP like a person would; return (link code, account id)."""
    form = {"name": name, "ein": "12-3456789", "state": "IN", "annual_budget": "42000"}
    if seed:
        form["seed"] = "1"
    r = client.post("/signup", data=form)
    code = re.search(r"class='code'>([A-Z2-9]{8})<", r.text)
    account_id = re.search(r"/a/(acct_[0-9a-f]{12})", r.text)
    return (code.group(1) if code else ""), (account_id.group(1) if account_id else "")


def last(chat: str = "") -> str:
    for key, text in reversed(SENT):
        if not chat or key == chat:
            return text
    return ""


def main() -> int:
    _sandbox()
    client = TestClient(webhook.app)

    print("signup (web)")
    r = client.get("/")
    check("GET / serves the signup form", r.status_code == 200 and "Create our books" in r.text)

    garden_code, garden_id = sign_up(client, "Riverside Garden Collective")
    shelter_code, shelter_id = sign_up(client, "Eastside Animal Shelter")
    check("two orgs sign up and get codes", bool(garden_code and shelter_code and garden_id != shelter_id),
          f"{garden_code} / {shelter_code}")

    r = client.post("/signup", data={"name": "  "})
    check("a nameless org is rejected", r.status_code == 400)

    print("\nlinking: an unlinked phone gets nowhere near an agent")
    SENT.clear()
    post_telegram(client, 555, "whats the balance")
    check("unlinked phone is told to sign up", "sign up at" in last().lower(), last()[:60])

    post_telegram(client, 555, "AAAAAAAA")
    check("a wrong code is refused", "doesn't match" in last(), last()[:60])

    post_telegram(client, 555, garden_code.lower())
    check("the right code links the phone", "linked to Riverside Garden Collective" in last(), last()[:60])

    post_telegram(client, 777, f" {shelter_code[:4]}-{shelter_code[4:]} ")
    check("a code survives being typed with spaces and a dash",
          "linked to Eastside Animal Shelter" in last(), last()[:60])

    print("\nthe thread: log -> confirm -> post")
    SENT.clear()
    post_telegram(client, 555, "paid 47 dollars for hoses")
    check("logs and reads the entry back", "$47.00" in last() and "confirm" in last().lower(), last())

    post_telegram(client, 555, "yes")
    check("posts on confirmation", "posted" in last().lower(), last())
    check("replies to the right chat", SENT[-1][0] == "telegram:555")

    print("\nisolation: the two orgs must not see each other")
    SENT.clear()
    post_telegram(client, 777, "yes")
    check("the other org's phone has nothing to confirm", "posted" not in last().lower(), last())

    from chest.store.ledger import LedgerStore

    garden, shelter = LedgerStore(garden_id), LedgerStore(shelter_id)
    check("the entry landed in the right books",
          garden.balance() != shelter.balance()
          and any("hose" in e.memo.lower() and e.amount == -47.0 for e in garden.posted())
          and not any(e.amount == -47.0 for e in shelter.posted()),
          f"garden ${garden.balance():,.2f} / shelter ${shelter.balance():,.2f}")

    SENT.clear()
    post_telegram(client, 777, "/whoami")
    check("each phone knows which books it keeps", "Eastside Animal Shelter" in last(), last()[:60])

    print("\nthread controls")
    SENT.clear()
    post_telegram(client, 555, "/reset")
    check("/reset keeps the account, drops the history",
          "fresh thread" in last().lower() and "Riverside" in last(), last())

    post_telegram(client, 555, "/unlink")
    post_telegram(client, 555, "whats the balance")
    check("/unlink puts the phone back outside", "sign up at" in last().lower(), last()[:60])

    r = client.post(
        "/telegram",
        json={"update_id": 101},
        headers={"X-Telegram-Bot-Api-Secret-Token": webhook.TELEGRAM_WEBHOOK_SECRET},
    )
    check("an update with no message is ignored", r.status_code == 200)

    print("\ndashboard")
    r = client.get(f"/a/{garden_id}")
    check("shows that org's balance and entries",
          r.status_code == 200 and "Riverside Garden Collective" in r.text and "hoses" in r.text.lower())
    check("does not leak the other org", "Eastside" not in r.text)
    r = client.get("/a/acct_doesnotexist")
    check("unknown account 404s", r.status_code == 404)

    print("\nwhatsapp (twilio form post -> twiml)")
    form = {"From": "whatsapp:+15551234567", "Body": "hi"}
    signature = RequestValidator(webhook.TWILIO_AUTH_TOKEN).compute_signature(
        "http://testserver/whatsapp", form
    )
    r = client.post(
        "/whatsapp",
        data=form,
        headers={"X-Twilio-Signature": signature},
    )
    check("answers in twiml", r.status_code == 200 and "<Response><Message>" in r.text, r.text[:70])

    print("\nimessage (blooio, hmac-signed)")
    secret = webhook.BLOOIO_WEBHOOK_SECRET

    def post_imessage(payload: dict, signature: str | None = None):
        raw = client.build_request("POST", "/imessage", json=payload).content
        if signature is None and secret:
            signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        headers = {"content-type": "application/json"}
        if signature is not None:
            headers["X-Blooio-Signature"] = signature
        return client.post("/imessage", content=raw, headers=headers)

    SENT.clear()
    r = post_imessage(blooio_event("+15551234567", "hello"))
    check("accepts a real message", r.status_code == 200 and bool(SENT))

    r = post_imessage(blooio_event("+15551234567", "hi"), signature="deadbeef")
    check("rejects a bad signature", r.status_code == 401, f"status {r.status_code}")

    SENT.clear()
    r = post_imessage({"event": "message.delivered", "data": {}})
    check("ignores non-message events", r.status_code == 200 and not SENT)

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
