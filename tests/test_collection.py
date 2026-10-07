from datetime import timedelta
from unittest.mock import MagicMock

import feedparser
import pytest

from src.collector import CollectionError, collect_articles, entry_timestamp, normalize_entry
from src.config import Config
from src.filters import filter_candidates, filter_recent, keyword_hits
from src.models import NewsSource
from src.utils import normalize_url, plain_text

SOURCE = NewsSource(name="Example RSS", url="https://example.com/feed", category="aviation")


def test_boundary_timezone_and_future_filter(article, now):
    boundary = article.model_copy(update={"published_at": now - timedelta(hours=24)})
    old = article.model_copy(update={"published_at": now - timedelta(hours=24, seconds=1)})
    future = article.model_copy(update={"published_at": now + timedelta(seconds=1)})
    assert filter_recent([boundary, old, future, article], now, 24) == [boundary, article]


def test_rss_normalization_strips_html_and_keeps_original_attribution(now):
    entry = {
        "title": "Airline &amp; AI pilot",
        "link": "https://EXAMPLE.com/news?utm_source=feed&id=2#top",
        "summary": "<p>New <b>system</b></p><script>ignore()</script>",
        "published": "Wed, 07 Oct 2026 08:00:00 +0300",
        "updated": "Wed, 07 Oct 2026 10:00:00 +0300",
        "source": {"title": "Original Publisher"},
    }
    article = normalize_entry(entry, SOURCE, now)
    assert article.title == "Airline & AI pilot"
    assert article.description == "New system"
    assert article.url == "https://example.com/news?id=2"
    assert article.published_at == now
    assert article.source == "Original Publisher"
    assert article.feed_name == SOURCE.name


@pytest.mark.parametrize(
    "bad_url", ["javascript:alert(1)", "relative/news", "", "https://a:b@host/x"]
)
def test_invalid_article_links_rejected(bad_url):
    with pytest.raises(ValueError):
        normalize_url(bad_url)


def test_canonical_url_preserves_meaningful_parameters():
    assert normalize_url("https://EXAMPLE.com:443/News?z=2&id=1&utm_campaign=x#part") == (
        "https://example.com/News?id=1&z=2"
    )
    assert normalize_url("https://example.com/News?id=2") != normalize_url(
        "https://example.com/News?id=1"
    )


def test_missing_timestamp_not_assumed_fresh():
    with pytest.raises(ValueError):
        entry_timestamp({})


def test_atom_iso_timestamp_from_feedparser(now):
    parsed = feedparser.parse(b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
      <title>Example</title><entry><title>Airline news</title><id>1</id>
      <link href="https://example.com/news"/><published>2026-10-07T08:00:00+03:00</published>
      </entry></feed>""")
    assert entry_timestamp(parsed.entries[0]) == now


def test_failed_feed_does_not_discard_good_feed(monkeypatch, now):
    xml = b"""<rss version="2.0"><channel><title>Feed</title><item>
      <title>Airline introduces AI pilot</title><link>https://example.com/news</link>
      <pubDate>Wed, 07 Oct 2026 05:00:00 GMT</pubDate></item>
      <item><title>Missing URL</title></item></channel></rss>"""
    second = SOURCE.model_copy(update={"name": "Broken"})

    def fetch(session, source, config):
        if source.name == "Broken":
            raise CollectionError("timeout")
        return xml

    monkeypatch.setattr("src.collector.fetch_feed", fetch)
    articles = collect_articles([SOURCE, second], Config(), now)
    assert len(articles) == 1
    monkeypatch.setattr("src.collector.fetch_feed", MagicMock(side_effect=CollectionError()))
    with pytest.raises(CollectionError, match="All RSS"):
        collect_articles([SOURCE], Config(), now)


def test_keyword_boundaries_and_noise(article):
    assert keyword_hits("chair and stairs", ("ai",)) == 0
    assert keyword_hits("AI agents", ("ai",)) == 1
    review = article.model_copy(update={"title": "Hands-on review of an AI phone"})
    generic = article.model_copy(update={"title": "Celebrity gossip", "description": ""})
    valid = article.model_copy(update={"title": "Airline optimizes customer service"})
    assert filter_candidates([review, generic, valid], 40) == [valid]
    assert plain_text("<p>A &amp; B</p>") == "A & B"
