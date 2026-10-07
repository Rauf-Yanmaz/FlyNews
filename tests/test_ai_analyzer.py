import json
from unittest.mock import MagicMock

import pytest

from src.ai_analyzer import AnalysisError, GeminiAnalyzer, validate_response
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
    assert (
        call.kwargs["json"]["generationConfig"]["responseFormat"]["text"]["schema"]["type"]
        == "array"
    )


def test_truncated_response_rejected(article):
    session = MagicMock()
    session.post.return_value.status_code = 200
    session.post.return_value.json.return_value = {
        "candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "[]"}]}}],
    }
    assert GeminiAnalyzer(Config(), session)._request([article]) == ""
