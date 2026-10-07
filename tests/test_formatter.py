import pytest

from src.formatter import format_digest, format_item, telegram_length


def test_html_escaped_and_length_uses_decoded_text(article, now):
    article.analysis.title_tr = '<fake> & "pilot"'
    article.source = "A & B"
    article.url = "https://example.com/news?a=1&b=2"
    text = format_digest([article], now)[0].text
    assert "&lt;fake&gt; &amp; &quot;pilot&quot;" in text
    assert "Kaynak: A &amp; B" in text
    assert 'href="https://example.com/news?a=1&amp;b=2"' in text
    assert telegram_length("<b>A &amp; B 🤖</b>") == 8


def test_messages_split_only_at_complete_item_boundaries(article, now):
    articles = []
    for index in range(10):
        item = article.model_copy(deep=True)
        item.id = str(index)
        item.analysis.summary = "A" * 450
        item.analysis.why_it_matters_for_ajet = "B" * 350
        item.analysis.possible_ajet_use_case = "C" * 350
        articles.append(item)
    messages = format_digest(articles, now)
    assert len(messages) > 1
    assert [identifier for message in messages for identifier in message.article_ids] == [
        str(index) for index in range(10)
    ]
    for message in messages:
        assert telegram_length(message.text) <= 4096
        for identifier in message.article_ids:
            assert format_item(articles[int(identifier)], int(identifier) + 1) in message.text


def test_oversize_item_never_silently_cut(article, now):
    with pytest.raises(ValueError, match="complete news item"):
        format_digest([article], now, max_length=100)


def test_turkish_date_uses_istanbul_day(article, now):
    instant = now.replace(hour=22)
    assert "8 Ekim 2026" in format_digest([article], instant)[0].text
    assert format_digest([], now) == []
