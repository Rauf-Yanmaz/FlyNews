from unittest.mock import MagicMock

import pytest
import requests

from src.config import Config
from src.database import Database, StateError
from src.formatter import DigestMessage
from src.telegram_publisher import AmbiguousDelivery, PublishError, TelegramPublisher


def config(path="data/news.db"):
    return Config(database_path=path, telegram_chat_id="@test", telegram_bot_token="secret")


def test_partial_publish_resumes_only_unsent_and_history_survives_reopen(tmp_path, article, now):
    path = str(tmp_path / "state.db")
    publisher = TelegramPublisher(config(path), MagicMock())
    publisher.send_message = MagicMock(side_effect=[42, PublishError("rejected")])
    with Database(path) as database:
        database.bind_channel("@test")
        database.save_articles([article], now)
        database.enqueue(
            [DigestMessage("First", (article.id,)), DigestMessage("Second", ())], "@test", now
        )
        with pytest.raises(PublishError):
            publisher.publish_pending(database)
        assert len(database.pending_messages()) == 1
        assert database.history(now, 30)[0][1] is True
    with Database(path) as database:
        publisher.send_message = MagicMock(return_value=43)
        assert publisher.publish_pending(database) == 1
        publisher.send_message.assert_called_once_with("Second")
        assert publisher.publish_pending(database) == 0
        with pytest.raises(StateError, match="Channel differs"):
            database.bind_channel("@different")


def test_ambiguous_delivery_blocks_resends_until_explicit_reconciliation(now):
    publisher = TelegramPublisher(config(), MagicMock())
    publisher.send_message = MagicMock(side_effect=AmbiguousDelivery("unknown"))
    with Database(":memory:") as database:
        database.enqueue([DigestMessage("Message", ())], "@test", now)
        with pytest.raises(AmbiguousDelivery):
            publisher.publish_pending(database)
        row = database.pending_messages()[0]
        assert row["status"] == "uncertain"
        with pytest.raises(StateError, match="ambiguous"):
            publisher.publish_pending(database)
        assert publisher.send_message.call_count == 1
        database.resolve(row["id"], "sent", 100)
        assert database.pending_messages() == []


def test_interrupted_sending_requires_reconciliation(now):
    with Database(":memory:") as database:
        database.enqueue([DigestMessage("Message", ())], "@test", now)
        identifier = database.pending_messages()[0]["id"]
        database.set_status(identifier, "sending")
        with pytest.raises(StateError):
            TelegramPublisher(config(), MagicMock()).publish_pending(database)
        database.resolve(identifier, "retry")
        assert database.pending_messages()[0]["status"] == "pending"


def response(status, data):
    result = MagicMock()
    result.status_code = status
    result.json.return_value = data
    return result


def test_telegram_429_retries_and_obeys_retry_after(monkeypatch):
    sleep = MagicMock()
    monkeypatch.setattr("src.telegram_publisher.time.sleep", sleep)
    session = MagicMock()
    session.post.side_effect = [
        response(429, {"ok": False, "error_code": 429, "parameters": {"retry_after": 3}}),
        response(200, {"ok": True, "result": {"message_id": 8}}),
    ]
    assert TelegramPublisher(config(), session).send_message("test") == 8
    sleep.assert_called_once_with(3)
    assert session.post.call_args.kwargs["json"]["parse_mode"] == "HTML"


@pytest.mark.parametrize(
    "error", [requests.ReadTimeout("token=secret"), requests.ConnectionError("token=secret")]
)
def test_ambiguous_transport_not_retried_or_secret_leaked(error):
    session = MagicMock()
    session.post.side_effect = error
    with pytest.raises(AmbiguousDelivery) as caught:
        TelegramPublisher(config(), session).send_message("test")
    assert "secret" not in str(caught.value)
    assert session.post.call_count == 1


def test_server_error_not_blindly_retried():
    session = MagicMock()
    session.post.return_value = response(503, {"ok": False})
    with pytest.raises(AmbiguousDelivery):
        TelegramPublisher(config(), session).send_message("test")
    assert session.post.call_count == 1
