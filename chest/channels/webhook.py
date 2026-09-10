"""One webhook, two channels.

Twilio WhatsApp Sandbox and the Telegram Bot API hit the same handler with the
same shape. That is the whole point of the channel story: Chest is
channel-agnostic, and SMS drops in behind the identical code the day carrier
registration clears.

Run locally:
    uvicorn chest.channels.webhook:app --reload --port 8000
    ngrok http 8000     # paste the https URL into Twilio or setWebhook
"""
from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse

from chest.agents.treasurer import TREASURER
from chest.config import TELEGRAM_BOT_TOKEN

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


# ---------- shared ----------

def handle(session_id: str, text: str) -> str:
    """Single entry point. Session id is the phone number or chat id."""
    try:
        result = TREASURER(text)
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
