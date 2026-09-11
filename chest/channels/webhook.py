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

import httpx
from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from chest.agents.treasurer import build_treasurer
from chest.config import BLOOIO_API_KEY, BLOOIO_FROM_NUMBER, BLOOIO_WEBHOOK_SECRET, TELEGRAM_BOT_TOKEN

app = FastAPI(title="Chest")


@app.get("/health")
def health():
    return {"ok": True}


# ---------- Twilio WhatsApp Sandbox ----------

@app.post("/whatsapp")
async def whatsapp(From: str = Form(""), Body: str = Form("")):
    reply = handle(session_id=From, text=Body)
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

    reply = handle(session_id=chat_id, text=text)
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

def handle(session_id: str, text: str) -> str:
    """Single entry point. Session id is the phone number or chat id."""
    try:
        result = build_treasurer(session_id)(text)
        return str(result)
    except Exception as exc:  # keep the thread alive; never 500 at a judge
        print(f"[error] {exc}")
        return "Something went wrong on my end. Try that again?"


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
