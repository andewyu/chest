"""One webhook, three channels.

Twilio WhatsApp Sandbox, the Telegram Bot API, and Blooio (iMessage) all hit
the same handler with the same shape. That is the whole point of the channel
story: Chest is channel-agnostic, and SMS drops in behind the identical code
the day carrier registration clears.

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
from fastapi.responses import PlainTextResponse
from twilio.request_validator import RequestValidator

from chest.agents.treasurer import build_treasurer, is_approval, is_edit
from chest.config import (
    BLOOIO_API_KEY,
    BLOOIO_FROM_NUMBER,
    BLOOIO_WEBHOOK_SECRET,
    PUBLIC_BASE_URL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_WEBHOOK_SECRET,
    TWILIO_AUTH_TOKEN,
)
from chest.store.drafts import DraftStore

app = FastAPI(title="Chest")
MAX_MESSAGE_CHARS = 4000
DRAFTS = DraftStore()


@app.get("/health")
def health():
    return {"ok": True}


# ---------- Twilio WhatsApp Sandbox ----------

@app.post("/whatsapp")
async def whatsapp(
    request: Request,
    From: str = Form(""),
    Body: str = Form(""),
    x_twilio_signature: str = Header(default=""),
):
    if not TWILIO_AUTH_TOKEN:
        raise HTTPException(status_code=503, detail="WhatsApp webhook is not configured")
    form = dict(await request.form())
    webhook_url = f"{PUBLIC_BASE_URL}/whatsapp" if PUBLIC_BASE_URL else str(request.url)
    # Twilio requires validating the complete URL and every form field with
    # its official helper: https://www.twilio.com/docs/usage/security#validating-requests
    if not RequestValidator(TWILIO_AUTH_TOKEN).validate(
        webhook_url, form, x_twilio_signature
    ):
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    _validate_message(From, Body)
    reply = handle(session_id=From, text=Body)
    return PlainTextResponse(
        f"<Response><Message>{_escape(reply)}</Message></Response>",
        media_type="application/xml",
    )


# ---------- Telegram ----------

@app.post("/telegram")
async def telegram(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default=""),
):
    if not TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Telegram webhook is not configured")
    if not hmac.compare_digest(
        x_telegram_bot_api_secret_token, TELEGRAM_WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=401, detail="invalid webhook secret")
    update = await request.json()
    msg = update.get("message") or update.get("edited_message") or {}
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    text = msg.get("text", "")
    if not chat_id or not text:
        return {"ok": True}

    _validate_message(chat_id, text)
    reply = handle(session_id=chat_id, text=text)
    send_telegram(chat_id, reply)
    return {"ok": True}


def send_telegram(chat_id: str, text: str) -> None:
    """Also used by the background sweep to push a proactive nudge."""
    if not TELEGRAM_BOT_TOKEN:
        print(f"[telegram:{chat_id}] {text}")
        return
    # Telegram limits sendMessage text to 4,096 characters. Keep a little
    # headroom and preserve paragraphs when possible so a grant draft does not
    # fail after the expensive agent run has already completed.
    for chunk in _message_chunks(text):
        response = httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": chunk},
            timeout=15,
        )
        response.raise_for_status()


# ---------- iMessage (Blooio) ----------
#
# Blooio is a third-party relay that sends real blue-bubble iMessages over a
# REST API — it is not an Apple-sanctioned API (Apple publishes none). See
# the honesty note in README.md.

@app.post("/imessage")
async def imessage(request: Request, x_blooio_signature: str = Header(default="")):
    body = await request.body()
    if not BLOOIO_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="iMessage webhook is not configured")
    if not _verify_blooio_signature(body, x_blooio_signature):
        raise HTTPException(status_code=401, detail="bad signature")

    payload = await request.json()
    if payload.get("event") != "message.received":
        return {"ok": True}

    data = payload.get("data") or {}
    chat_id = data.get("from", "")
    text = data.get("text", "")
    if not chat_id or not text:
        return {"ok": True}

    _validate_message(chat_id, text)
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
    response = httpx.post(
        f"https://api.blooio.com/v2/api/chats/{quote(chat_id, safe='')}/messages",
        headers={"Authorization": f"Bearer {BLOOIO_API_KEY}"},
        json=payload,
        timeout=15,
    )
    response.raise_for_status()


# ---------- shared ----------

def handle(session_id: str, text: str) -> str:
    """Single entry point. Session id is the phone number or chat id."""
    try:
        has_pending_draft = DRAFTS.has_pending(session_id)
        if has_pending_draft and is_approval(text):
            DRAFTS.approve(session_id)
            return "Draft approved for human filing. Chest did not submit it."
        if has_pending_draft and is_edit(text):
            instructions = re.sub(r"^\s*edit\s*:?\s*", "", text, flags=re.I)
            DRAFTS.request_edit(session_id, instructions or "No details provided")
            return "Revision request saved. Chest did not submit the draft."
        result = build_treasurer(session_id)(text)
        return str(result)
    except Exception as exc:  # keep the thread alive; never 500 at a judge
        print(f"[error] {exc}")
        return "Something went wrong on my end. Try that again?"


def _validate_message(session_id: str, text: str) -> None:
    if not session_id.strip():
        raise HTTPException(status_code=422, detail="missing sender")
    if not text.strip():
        raise HTTPException(status_code=422, detail="empty message")
    if len(text) > MAX_MESSAGE_CHARS:
        raise HTTPException(status_code=422, detail="message is too long")


def _message_chunks(text: str, limit: int = 4000) -> list[str]:
    """Split outbound text without losing or reordering any characters."""
    if not text:
        return [""]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit + 1)
        if split_at <= 0:
            split_at = limit
        else:
            split_at += 1
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
    chunks.append(remaining)
    return chunks


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
