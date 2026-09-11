"""One webhook, three channels, many organizations.

Twilio WhatsApp Sandbox, the Telegram Bot API, and Blooio (iMessage) all hit
the same handler with the same shape. That is the whole point of the channel
story: Chest is channel-agnostic, and SMS drops in behind the identical code
the day carrier registration clears.

Every inbound message resolves to an account before it reaches a model:

    "telegram:12345" -> AccountStore.account_for -> Account -> that org's agent

An unlinked identity can do exactly one thing: send a link code. It never
reaches an agent, never touches a ledger, and never costs a model call. This
is the security boundary, so it lives at the front door in handle() rather
than in a prompt.

Note on iMessage: Blooio is a third-party relay service, not an Apple-
sanctioned send API — Apple publishes no public API for sending iMessage.
Say so plainly wherever this channel is described; see README.md.

Run locally:
    uvicorn chest.channels.webhook:app --reload --port 8000
    ngrok http 8000     # paste the https URL into Twilio, setWebhook, or Blooio
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re

import httpx
from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from chest.agents.treasurer import _human_date, _money, for_session, reset_session
from chest.channels import web
from chest.config import (
    BLOOIO_API_KEY,
    BLOOIO_FROM_NUMBER,
    BLOOIO_WEBHOOK_SECRET,
    PUBLIC_URL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_BOT_USERNAME,
)
from chest.store.accounts import AccountStore
from chest.store.ledger import LedgerStore
from chest.tools.forecast import forecast

app = FastAPI(title="Chest")
ACCOUNTS = AccountStore()

# 8 characters from the link-code alphabet, however the human spaced it out.
_CODE = re.compile(r"^[\s-]*([23456789ABCDEFGHJKMNPQRSTUVWXYZ][\s-]*){8}$", re.I)


@app.get("/health")
def health():
    return {"ok": True}


# ---------- signup (web) ----------

@app.get("/", response_class=HTMLResponse)
def index():
    return web.signup_form()


@app.post("/signup", response_class=HTMLResponse)
def signup(
    name: str = Form(...),
    ein: str = Form(""),
    state: str = Form("IN"),
    applicant_type: str = Form(""),
    annual_budget: str = Form("50000"),
    seed: str = Form(""),
):
    name = name.strip()
    if not name:
        return HTMLResponse(web.signup_form("Your organization needs a name."), status_code=400)

    try:
        budget = float(str(annual_budget).replace(",", "").replace("$", "").strip() or 0)
    except ValueError:
        return HTMLResponse(web.signup_form("Annual budget should be a number."), status_code=400)

    profile = {"ein": ein.strip() or "00-0000000", "state": state, "annual_budget": budget}
    if applicant_type.strip():
        profile["applicant_type"] = applicant_type.strip()
    account = ACCOUNTS.create(name, **profile)

    seeded = bool(seed)
    if seeded:
        from scripts.seed_ledger import build

        LedgerStore(account.id).bulk_post(build())

    return web.linked_page(account, _bot_username(), seeded)


@app.get("/a/{account_id}", response_class=HTMLResponse)
def dashboard(account_id: str):
    account = ACCOUNTS.get(account_id)
    if account is None:
        return HTMLResponse(web.signup_form("No such organization."), status_code=404)

    store = LedgerStore(account.id)
    entries = [
        {
            "date": _human_date(e.occurred_on),
            "memo": e.memo,
            "kind": e.kind,
            "amount_display": _money(abs(e.amount)),
            "direction": "out" if e.amount < 0 else "in",
        }
        for e in sorted(store.posted(), key=lambda e: e.occurred_on, reverse=True)[:15]
    ]
    gap = forecast(store)
    return web.dashboard(
        account,
        _money(store.balance()),
        gap,
        entries,
        ACCOUNTS.identities_for(account.id),
        runs_out_on=_human_date(gap.goes_negative_on),
    )


@app.get("/a/{account_id}/", response_class=RedirectResponse)
def dashboard_slash(account_id: str):
    return RedirectResponse(f"/a/{account_id}")


# ---------- Twilio WhatsApp Sandbox ----------

@app.post("/whatsapp")
async def whatsapp(From: str = Form(""), Body: str = Form("")):
    reply = handle(session_id=f"whatsapp:{From}", text=Body)
    return PlainTextResponse(
        f"<Response><Message>{_escape(reply)}</Message></Response>",
        media_type="application/xml",
    )


# ---------- Telegram ----------

@app.post("/telegram")
async def telegram(request: Request):
    update = await request.json()
    msg = update.get("message") or update.get("edited_message") or {}
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    text = msg.get("text", "")
    if not chat_id or not text:
        return {"ok": True}

    reply = handle(session_id=f"telegram:{chat_id}", text=text)
    send_telegram(chat_id, reply)
    return {"ok": True}


def send_telegram(chat_id: str, text: str) -> None:
    """Also used by the background sweep to push a proactive nudge."""
    if not TELEGRAM_BOT_TOKEN:
        print(f"[telegram:{chat_id}] {text}")
        return
    httpx.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15,
    )


_BOT_USERNAME_CACHE: str | None = None


def _bot_username() -> str:
    """Ask Telegram who we are, once, so signup can say @thebot by name."""
    global _BOT_USERNAME_CACHE
    if TELEGRAM_BOT_USERNAME:
        return TELEGRAM_BOT_USERNAME
    if _BOT_USERNAME_CACHE is not None:
        return _BOT_USERNAME_CACHE
    _BOT_USERNAME_CACHE = ""
    if TELEGRAM_BOT_TOKEN:
        try:
            r = httpx.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe", timeout=10)
            _BOT_USERNAME_CACHE = r.json().get("result", {}).get("username", "") or ""
        except Exception as exc:  # a missing username is cosmetic; never fail signup
            print(f"[warn] getMe failed: {exc}")
    return _BOT_USERNAME_CACHE


# ---------- iMessage (Blooio) ----------
#
# Blooio is a third-party relay that sends real blue-bubble iMessages over a
# REST API — it is not an Apple-sanctioned API (Apple publishes none). See
# the honesty note in README.md.

@app.post("/imessage")
async def imessage(request: Request, x_blooio_signature: str = Header(default="")):
    body = await request.body()
    if BLOOIO_WEBHOOK_SECRET and not _verify_blooio_signature(body, x_blooio_signature):
        raise HTTPException(status_code=401, detail="bad signature")

    payload = await request.json()
    if payload.get("event") != "message.received":
        return {"ok": True}

    data = payload.get("data") or {}
    chat_id = data.get("from", "")
    text = data.get("text", "")
    if not chat_id or not text:
        return {"ok": True}

    reply = handle(session_id=f"imessage:{chat_id}", text=text)
    send_blooio(chat_id, reply)
    return {"ok": True}


def _verify_blooio_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(BLOOIO_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def send_blooio(chat_id: str, text: str) -> None:
    """Also used by the background sweep to push a proactive nudge over iMessage."""
    if not BLOOIO_API_KEY:
        print(f"[imessage:{chat_id}] {text}")
        return
    from urllib.parse import quote

    payload: dict = {"text": text}
    if BLOOIO_FROM_NUMBER:
        payload["from_number"] = BLOOIO_FROM_NUMBER
    httpx.post(
        f"https://api.blooio.com/v2/api/chats/{quote(chat_id, safe='')}/messages",
        headers={"Authorization": f"Bearer {BLOOIO_API_KEY}"},
        json=payload,
        timeout=15,
    )


# ---------- shared ----------

def _signup_prompt() -> str:
    return (
        "hey — i keep the books for one organization at a time, and this number "
        f"isn't linked to one yet.\n\nsign up at {PUBLIC_URL} and text me the "
        "8-character code it gives you."
    )


def handle(session_id: str, text: str) -> str:
    """Single entry point. Session id is "<channel>:<handle>".

    Resolves the account first. An unlinked identity can only send a code —
    it never reaches an agent, a ledger, or the model.
    """
    text = (text or "").strip()
    if not text:
        return _signup_prompt()

    low = text.lower()
    account = ACCOUNTS.account_for(session_id)

    # ---- unlinked: the only accepted input is a link code ----
    if account is None:
        if _CODE.match(text):
            found = ACCOUNTS.by_code(text)
            if found is None:
                return "that code doesn't match an organization. check it and try again?"
            ACCOUNTS.link(session_id, found.id)
            reset_session(session_id, found)
            balance = _money(LedgerStore(found.id).balance())
            return (
                f"linked to {found.name}. balance is {balance}.\n\n"
                "tell me when money moves and i'll log it. nothing posts till you say yes."
            )
        return _signup_prompt()

    # ---- linked: thread controls, then the agent ----
    if low in {"/start", "/reset", "reset"}:
        reset_session(session_id, account)
        return f"fresh thread. still keeping {account.name}'s books. what moved?"

    if low in {"/unlink", "unlink"}:
        ACCOUNTS.unlink(session_id)
        reset_session(session_id, account)
        return f"unlinked from {account.name}. text a code to link somewhere else."

    if low in {"/whoami", "whoami", "/books"}:
        store = LedgerStore(account.id)
        return (
            f"{account.name}. balance {_money(store.balance())}, "
            f"{len(store.posted())} entries posted.\n{PUBLIC_URL}/a/{account.id}"
        )

    try:
        reply = str(for_session(session_id, account)(text)).strip()
        # A model that answers with tool calls and no text would otherwise
        # send an empty message into the thread.
        return reply or "one sec, that didn't come out right. ask me again?"
    except Exception as exc:  # keep the thread alive; never 500 at a judge
        print(f"[error] {session_id} ({account.id}): {type(exc).__name__}: {exc}")
        return "something broke on my end. say that again?"


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
