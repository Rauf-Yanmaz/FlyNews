from unittest.mock import MagicMock

import pytest

from src.config import Config
from src.database import Database
from src.main import main, run_pipeline


def test_complete_pipeline_mocked_and_rerun_does_not_repost(tmp_path, article, monkeypatch):
    path = str(tmp_path / "news.db")
    fresh = article.model_copy(update={"analysis": None})
    monkeypatch.setattr("src.main.utc_now", lambda: article.collected_at)
    monkeypatch.setattr("src.main.collect_articles", lambda *args: [fresh])
    analyze = MagicMock(return_value=[article])
    monkeypatch.setattr("src.main.GeminiAnalyzer.analyze", analyze)
    send = MagicMock(return_value=123)
    monkeypatch.setattr("src.main.TelegramPublisher.send_message", send)
    settings = Config(
        database_path=path,
        gemini_api_key="test",
        gemini_model="test-model",
        telegram_bot_token="test",
        telegram_chat_id="@test",
    )
    assert run_pipeline(settings) == 0
    assert run_pipeline(settings) == 0
    assert analyze.call_count == 1
    assert send.call_count == 1
    with Database(path) as database:
        assert database.history(article.collected_at, 30)[0][1]


def test_dry_run_never_publishes_or_mutates_database(tmp_path, article, monkeypatch, capsys):
    path = tmp_path / "must-not-exist.db"
    monkeypatch.setattr("src.main.utc_now", lambda: article.collected_at)
    monkeypatch.setattr("src.main.collect_articles", lambda *args: [article])
    publish = MagicMock()
    monkeypatch.setattr("src.main.TelegramPublisher.publish_pending", publish)
    settings = Config(
        database_path=str(path), gemini_api_key="test", gemini_model="test-model", dry_run=True
    )
    assert run_pipeline(settings) == 0
    assert not path.exists()
    publish.assert_not_called()
    assert "AJet" in capsys.readouterr().out


def test_offline_demo_needs_no_credentials_and_is_labeled(monkeypatch, capsys):
    monkeypatch.setattr("src.main.Config.from_env", lambda: Config())
    assert main(["--demo", "--dry-run"]) == 0
    assert "Gerçek haber değildir" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["--demo"])


def test_missing_credentials_fail_clearly(monkeypatch, caplog):
    monkeypatch.setattr("src.main.Config.from_env", lambda: Config())
    assert main(["--dry-run"]) == 1
    assert "GEMINI_API_KEY" in caplog.text


def test_invalid_cli_limits_validated(monkeypatch):
    monkeypatch.setattr("src.main.Config.from_env", lambda: Config())
    assert main(["--dry-run", "--limit", "0"]) == 1


def test_multiple_current_headlines_reusing_one_cached_item_publish_once(
    tmp_path,
    article,
    monkeypatch,
):
    path = str(tmp_path / "cached.db")
    with Database(path) as database:
        database.save_articles([article], article.collected_at)
    first = article.model_copy(
        update={
            "id": "first",
            "url": "https://example.com/first",
            "analysis": None,
            "title": "Airline announces biometric boarding",
        }
    )
    second = article.model_copy(
        update={
            "id": "second",
            "url": "https://example.com/second",
            "analysis": None,
            "title": "AI customer service software announced",
        }
    )
    monkeypatch.setattr("src.main.utc_now", lambda: article.collected_at)
    monkeypatch.setattr("src.main.collect_articles", lambda *args: [first, second])
    monkeypatch.setattr("src.main.same_story", lambda *args: True)
    analyze = MagicMock()
    monkeypatch.setattr("src.main.GeminiAnalyzer.analyze", analyze)
    send = MagicMock(return_value=123)
    monkeypatch.setattr("src.main.TelegramPublisher.send_message", send)
    settings = Config(
        database_path=path,
        gemini_api_key="test",
        gemini_model="test-model",
        telegram_bot_token="test",
        telegram_chat_id="@test",
    )
    assert run_pipeline(settings) == 0
    analyze.assert_not_called()
    assert send.call_args.args[0].count("<b>Ne oldu?</b>") == 1
