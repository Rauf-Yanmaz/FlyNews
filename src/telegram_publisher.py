"""Publish known-unsent messages; never blindly retry ambiguous deliveries."""

import logging
import time

import requests

from src.config import Config
from src.database import Database, StateError
from src.formatter import telegram_length

logger = logging.getLogger(__name__)


class PublishError(RuntimeError):
    pass


class AmbiguousDelivery(PublishError):
    pass


class TelegramPublisher:
    def __init__(self, config: Config, session: requests.Session) -> None:
        self.config = config
        self.session = session

    def send_message(self, text: str) -> int:
        if not 1 <= telegram_length(text) <= 4096:
            raise PublishError("Message length is outside Telegram limits")
        endpoint = (
            "https://api.telegram.org/bot"
            + self.config.telegram_bot_token.get_secret_value()
            + "/sendMessage"
        )
        for attempt in range(self.config.request_attempts):
            try:
                response = self.session.post(
                    endpoint,
                    json={
                        "chat_id": self.config.telegram_chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "link_preview_options": {"is_disabled": True},
                    },
                    timeout=(10, self.config.http_timeout_seconds),
                )
            except requests.ConnectTimeout:
                # Connection establishment failed before sending a request; safe to retry.
                if attempt + 1 < self.config.request_attempts:
                    time.sleep(min(2**attempt, self.config.max_retry_delay_seconds))
                    continue
                raise PublishError("Telegram connection establishment timed out") from None
            except requests.RequestException:
                raise AmbiguousDelivery("Telegram delivery could not be confirmed") from None
            try:
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError
            except (ValueError, TypeError):
                raise AmbiguousDelivery("Telegram returned an unreadable response") from None
            if response.status_code >= 500:
                raise AmbiguousDelivery("Telegram server error; delivery could not be confirmed")
            if data.get("ok") is True:
                message_id = data.get("result", {}).get("message_id")
                if type(message_id) is not int:
                    raise AmbiguousDelivery("Telegram confirmation lacked a message ID")
                return message_id
            if data.get("ok") is not False:
                raise AmbiguousDelivery("Telegram returned an unexpected response")
            error_code = data.get("error_code", response.status_code)
            if type(error_code) is not int:
                raise AmbiguousDelivery("Telegram returned an invalid error code")
            if error_code == 429 and attempt + 1 < self.config.request_attempts:
                try:
                    delay = max(1.0, float(data.get("parameters", {}).get("retry_after", 2)))
                except (ValueError, TypeError, AttributeError):
                    raise PublishError("Invalid Telegram retry delay") from None
                if delay > self.config.max_retry_delay_seconds:
                    raise PublishError("Telegram retry delay exceeds run budget; resume next run")
                time.sleep(delay)
                continue
            raise PublishError(f"Telegram rejected message (code {error_code})")
        raise PublishError("Telegram retries exhausted")

    def publish_pending(self, database: Database) -> int:
        pending = database.pending_messages()
        if any(row["status"] in {"sending", "uncertain"} for row in pending):
            raise StateError(
                "An earlier Telegram delivery is ambiguous. Inspect --outbox-status and "
                "resolve it after checking the channel; publication is paused to avoid duplicates",
            )
        sent = 0
        for row in pending:
            if row["chat_id"] != self.config.telegram_chat_id:
                raise StateError("Outbox destination differs from configured channel")
            database.set_status(row["id"], "sending")  # Commit BEFORE making the HTTP request.
            try:
                message_id = self.send_message(row["text"])
            except AmbiguousDelivery:
                database.set_status(row["id"], "uncertain")
                raise
            except PublishError:
                database.set_status(row["id"], "pending")
                raise
            # If interrupted here, 'sending' persists and requires manual reconciliation.
            database.mark_sent(row["id"], message_id)
            sent += 1
            logger.info("Telegram message confirmed: %s", row["id"][:12])
            if sent < len(pending):
                time.sleep(1.1)
        return sent
