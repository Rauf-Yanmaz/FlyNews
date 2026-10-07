"""Fetch bounded RSS metadata; never scrape article bodies."""

import calendar
import logging
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import feedparser
import requests

from src.config import Config
from src.models import Article, NewsSource
from src.utils import fingerprint, normalize_url, plain_text

logger = logging.getLogger(__name__)
MAX_FEED_BYTES = 5_000_000


class CollectionError(RuntimeError):
    pass


def entry_timestamp(entry: dict) -> datetime:
    # Prefer publication over modification. Missing dates are not treated as fresh news.
    for name in ("published", "created", "updated"):
        raw = entry.get(name)
        if isinstance(raw, str):
            try:
                value = parsedate_to_datetime(raw)
                if value.tzinfo is not None:
                    return value.astimezone(UTC)
            except (ValueError, TypeError, OverflowError):
                pass
        parsed = entry.get(f"{name}_parsed")
        if parsed:
            try:
                return datetime.fromtimestamp(calendar.timegm(parsed), UTC)
            except (ValueError, TypeError, OverflowError):
                pass
    raise ValueError("No usable timestamp")


def normalize_entry(entry: dict, source: NewsSource, now: datetime) -> Article:
    title = plain_text(entry.get("title", ""), 500)
    url = normalize_url(entry.get("link", ""))
    description = plain_text(entry.get("summary", entry.get("description", "")))
    attribution = entry.get("source", {}).get("title") or source.name
    source_name = plain_text(attribution, 120) or source.name
    return Article(
        id=fingerprint(url),
        hash=fingerprint(url),
        title=title,
        url=url,
        description=description,
        source=source_name,
        feed_name=source.name,
        category=source.category,
        priority=source.priority,
        published_at=entry_timestamp(entry),
        collected_at=now,
    )


def fetch_feed(session: requests.Session, source: NewsSource, config: Config) -> bytes:
    for attempt in range(config.request_attempts):
        try:
            with session.get(
                source.url,
                timeout=(10, config.http_timeout_seconds),
                stream=True,
                headers={"User-Agent": "FlyNews/0.1 (RSS intelligence digest)"},
            ) as response:
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt + 1 < config.request_attempts:
                        time.sleep(min(2**attempt, config.max_retry_delay_seconds))
                        continue
                response.raise_for_status()
                chunks = bytearray()
                for chunk in response.iter_content(64_000):
                    chunks.extend(chunk)
                    if len(chunks) > MAX_FEED_BYTES:
                        raise CollectionError("Feed exceeds size limit")
                return bytes(chunks)
        except requests.RequestException:
            if attempt + 1 < config.request_attempts:
                time.sleep(min(2**attempt, config.max_retry_delay_seconds))
    raise CollectionError("RSS request failed")


def collect_articles(
    sources: list[NewsSource],
    config: Config,
    now: datetime,
) -> list[Article]:
    articles = []
    successful_feeds = 0
    with requests.Session() as session:
        for source in sources:
            try:
                parsed = feedparser.parse(fetch_feed(session, source, config))
                if not parsed.get("version"):
                    raise CollectionError("Response is not RSS or Atom")
                successful_feeds += 1
                if parsed.get("bozo"):
                    logger.warning("Feed has parsing defects: %s", source.name)
                for entry in parsed.entries[: config.max_feed_entries]:
                    try:
                        articles.append(normalize_entry(entry, source, now))
                    except (ValueError, TypeError, AttributeError, OverflowError):
                        logger.warning("Skipped malformed entry from %s", source.name)
            except (CollectionError, ValueError, TypeError):
                logger.warning("Failed to fetch or parse %s", source.name)
    if not successful_feeds:
        raise CollectionError("All RSS feeds failed; no digest generated")
    logger.info("Collected %d articles from %d feeds", len(articles), successful_feeds)
    return articles
