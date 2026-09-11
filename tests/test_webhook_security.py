from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from chest.channels import webhook


client = TestClient(webhook.app)


def test_whatsapp_rejects_an_invalid_twilio_signature(monkeypatch):
    monkeypatch.setattr(webhook, "TWILIO_AUTH_TOKEN", "test-token")

    response = client.post(
        "/whatsapp",
        data={"From": "whatsapp:+15551234567", "Body": "balance"},
        headers={"X-Twilio-Signature": "invalid"},
    )

    assert response.status_code == 401


def test_whatsapp_accepts_a_valid_twilio_signature(monkeypatch):
    token = "test-token"
    form = {"From": "whatsapp:+15551234567", "Body": "balance"}
    signature = RequestValidator(token).compute_signature(
        "http://testserver/whatsapp", form
    )
    monkeypatch.setattr(webhook, "TWILIO_AUTH_TOKEN", token)
    monkeypatch.setattr(webhook, "handle", lambda session_id, text: "safe reply")

    response = client.post(
        "/whatsapp", data=form, headers={"X-Twilio-Signature": signature}
    )

    assert response.status_code == 200
    assert "safe reply" in response.text


def test_telegram_requires_the_configured_webhook_secret(monkeypatch):
    monkeypatch.setattr(webhook, "TELEGRAM_WEBHOOK_SECRET", "telegram-secret")

    response = client.post(
        "/telegram",
        json={"message": {"chat": {"id": 123}, "text": "balance"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )

    assert response.status_code == 401


def test_telegram_accepts_the_configured_webhook_secret(monkeypatch):
    monkeypatch.setattr(webhook, "TELEGRAM_WEBHOOK_SECRET", "telegram-secret")
    monkeypatch.setattr(webhook, "handle", lambda session_id, text: "safe reply")
    monkeypatch.setattr(webhook, "send_telegram", lambda chat_id, text: None)

    response = client.post(
        "/telegram",
        json={"message": {"chat": {"id": 123}, "text": "balance"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret"},
    )

    assert response.status_code == 200


def test_telegram_rejects_oversized_messages(monkeypatch):
    monkeypatch.setattr(webhook, "TELEGRAM_WEBHOOK_SECRET", "telegram-secret")

    response = client.post(
        "/telegram",
        json={"message": {"chat": {"id": 123}, "text": "x" * 4001}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret"},
    )

    assert response.status_code == 422


def test_telegram_splits_long_replies(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

    monkeypatch.setattr(webhook, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(
        webhook.httpx,
        "post",
        lambda *args, **kwargs: calls.append(kwargs["json"]["text"]) or Response(),
    )

    webhook.send_telegram("chat-1", "a" * 8500)

    assert "".join(calls) == "a" * 8500
    assert len(calls) == 3
    assert all(len(chunk) <= 4000 for chunk in calls)
