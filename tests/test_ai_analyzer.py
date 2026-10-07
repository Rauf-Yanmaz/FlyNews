import json
from unittest.mock import MagicMock

import pytest

from src.ai_analyzer import (
    AnalysisConfigurationError,
    AnalysisError,
    GeminiAnalyzer,
    rejection_description,
    validate_response,
)
from src.config import Config


@pytest.mark.parametrize("raw", ["not json", "{}", "null", "```json\n[]\n```", "[null]"])
def test_malformed_ai_output_does_not_raise(raw, article):
    assert validate_response(raw, {article.id}) == {}


@pytest.mark.parametrize("bad_score", [0, 11, "9", 9.0, True])
def test_score_bounds_and_strict_integer(bad_score, article):
    value = article.analysis.model_dump()
    value["scores"]["ajet_relevance"] = bad_score
    assert validate_response(json.dumps([value]), {article.id}) == {}


def test_valid_sibling_preserved_unknown_and_duplicate_ids_rejected(article):
    valid = article.analysis.model_dump()
    invalid = valid | {"article_id": "other", "summary": ""}
    assert set(validate_response(json.dumps([valid, invalid]), {article.id, "other"})) == {
        article.id
    }
    assert validate_response(json.dumps([valid, valid]), {article.id}) == {}
    assert validate_response(json.dumps([valid]), {"unknown"}) == {}


def test_retry_once_for_missing_item_only(article, monkeypatch):
    monkeypatch.setattr("src.ai_analyzer.time.sleep", lambda seconds: None)
    second = article.model_copy(deep=True)
    second.id = "second"
    second.analysis.article_id = "second"
    valid = article.analysis.model_dump()
    analyzer = GeminiAnalyzer(Config(ai_batch_delay_seconds=0), MagicMock())
    analyzer._request = MagicMock(side_effect=[json.dumps([valid]), "invalid"])
    assert analyzer.analyze([article, second]) == [article]
    assert analyzer._request.call_count == 2
    assert [item.id for item in analyzer._request.call_args_list[1].args[0]] == ["second"]


def test_failed_batch_does_not_stop_next_batch(article, monkeypatch):
    monkeypatch.setattr("src.ai_analyzer.time.sleep", lambda seconds: None)
    analyzer = GeminiAnalyzer(Config(ai_batch_size=1, ai_batch_delay_seconds=0), MagicMock())
    second = article.model_copy(deep=True)
    second.id = "second"
    second.analysis.article_id = "second"
    analyzer._request = MagicMock(
        side_effect=[AnalysisError("timeout"), json.dumps([second.analysis.model_dump()])]
    )
    assert analyzer.analyze([article, second]) == [second]


def test_rest_payload_and_response_parsing(article):
    session = MagicMock()
    response = session.post.return_value
    response.status_code = 200
    text = json.dumps([article.analysis.model_dump()])
    response.json.return_value = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {
                    "parts": [
                        {"text": "private reasoning", "thought": True},
                        {"text": text},
                    ]
                },
            }
        ]
    }
    analyzer = GeminiAnalyzer(Config(gemini_api_key="secret", gemini_model="test-model"), session)
    assert analyzer._request([article]) == text
    call = session.post.call_args
    assert call.kwargs["headers"] == {"x-goog-api-key": "secret"}
    assert "secret" not in call.args[0]
    generation = call.kwargs["json"]["generationConfig"]
    assert generation["responseMimeType"] == "application/json"
    assert generation["responseJsonSchema"]["type"] == "array"
    assert "responseFormat" not in generation


def test_truncated_response_rejected(article):
    session = MagicMock()
    session.post.return_value.status_code = 200
    session.post.return_value.json.return_value = {
        "candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "[]"}]}}],
    }
    assert GeminiAnalyzer(Config(), session)._request([article]) == ""


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404])
def test_permanent_request_rejection_stops_later_batches(status, article, monkeypatch):
    sleep = MagicMock()
    monkeypatch.setattr("src.ai_analyzer.time.sleep", sleep)
    session = MagicMock()
    session.post.return_value.status_code = status
    session.post.return_value.json.return_value = {
        "error": {"message": "request rejected", "status": "INVALID_ARGUMENT"},
    }
    analyzer = GeminiAnalyzer(Config(ai_batch_size=1), session)
    with pytest.raises(AnalysisConfigurationError, match=f"HTTP {status}"):
        analyzer.analyze([article, article.model_copy(update={"id": "second"})])
    assert session.post.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize(
    "message,reason,expected",
    [
        ("API key not valid. Please pass a valid API key.", "API_KEY_INVALID", "is invalid"),
        ("Your API key was reported as leaked.", "", "blocked the API key"),
        ("Request rejected", "SERVICE_DISABLED", "enable the Generative Language API"),
        ("Request rejected", "API_KEY_HTTP_REFERRER_BLOCKED", "restrictions prevent"),
        ("Invalid value at generation_config.response_format.text.mime_type", "", "format/schema"),
    ],
)
def test_provider_diagnostics_are_actionable_without_logging_raw_text(message, reason, expected):
    response = MagicMock()
    response.status_code = 400
    response.json.return_value = {
        "error": {
            "message": message + " secret-key-should-never-be-logged",
            "details": [{"reason": reason, "metadata": {"api_key": "secret-key"}}],
        },
    }
    result = rejection_description(response)
    assert expected in result
    assert "secret-key" not in result


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"error": None},
        {"error": {"message": None}},
        {"error": {"message": "rejected", "details": None}},
    ],
)
def test_malformed_error_bodies_do_not_leak_or_crash(payload):
    response = MagicMock()
    response.status_code = 400
    response.json.return_value = payload
    assert "HTTP 400" in rejection_description(response)
