"""Run the Telegram bot with no tunnel, no ngrok, no public URL.

    python -m scripts.telegram_poll

Long-polls getUpdates and routes every message through the exact same
`handle()` the webhook uses, so what you test here is what deploys. Webhooks
and polling are mutually exclusive at Telegram's end, so this deletes any
registered webhook on start and says so.

Ctrl-C to stop. Add --once to drain what's waiting and exit.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from chest.channels.webhook import handle  # noqa: E402
from chest.config import (  # noqa: E402
    BEDROCK_MODEL_ID,
    CHEST_FAKE_MODEL,
    PUBLIC_URL,
    TELEGRAM_BOT_TOKEN,
)

API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def call(method: str, **params):
    r = httpx.post(f"{API}/{method}", json=params, timeout=40)
    return r.json()


def handle_update(update: dict) -> None:
    msg = update.get("message") or update.get("edited_message") or {}
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    text = msg.get("text", "")
    if not chat_id or not text:
        return

    who = (msg.get("from") or {}).get("first_name", "?")
    print(f"\n  \033[36m{who} ({chat_id}):\033[0m {text}")
    reply = handle(session_id=f"telegram:{chat_id}", text=text)
    print(f"  \033[32mchest:\033[0m {reply}")
    call("sendMessage", chat_id=chat_id, text=reply)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="drain pending updates and exit")
    args = ap.parse_args()

    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN is empty. Put the BotFather token in .env.")
        return 1

    me = httpx.get(f"{API}/getMe", timeout=15).json()
    if not me.get("ok"):
        print(f"Telegram rejected the token: {me}")
        return 1
    username = me["result"]["username"]

    hook = httpx.get(f"{API}/getWebhookInfo", timeout=15).json().get("result", {})
    if hook.get("url"):
        print(f"deleting registered webhook ({hook['url']}) — polling and webhooks can't both run")
        call("deleteWebhook")

    print(f"polling as @{username}")
    print(f"model: {BEDROCK_MODEL_ID}" + ("  (FAKE — plumbing only)" if CHEST_FAKE_MODEL else ""))
    print(f"signup page: {PUBLIC_URL}")
    print("\ntext the bot. ctrl-c to stop.")

    offset = None
    while True:
        try:
            params = {"timeout": 25}
            if offset is not None:
                params["offset"] = offset
            data = httpx.post(f"{API}/getUpdates", json=params, timeout=40).json()
        except httpx.HTTPError as exc:
            print(f"  [net] {exc}; retrying")
            time.sleep(3)
            continue
        except KeyboardInterrupt:
            print("\nstopped.")
            return 0

        updates = data.get("result", [])
        for update in updates:
            offset = update["update_id"] + 1
            try:
                handle_update(update)
            except Exception as exc:  # one bad message must not kill the loop
                print(f"  [error] {type(exc).__name__}: {exc}")

        if args.once and not updates:
            print("nothing pending.")
            return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nstopped.")
