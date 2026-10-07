"""Cheap, configurable filters before paid/rate-limited analysis."""

import re
from datetime import datetime, timedelta

from src.feeds import EXCLUDED_TITLE_PHRASES, RELEVANT_KEYWORDS
from src.models import Article


def filter_recent(articles: list[Article], now: datetime, hours: int) -> list[Article]:
    if now.tzinfo is None:
        raise ValueError("Reference time must have a timezone")
    cutoff = now - timedelta(hours=hours)
    return [article for article in articles if cutoff <= article.published_at <= now]


def keyword_hits(text: str, keywords: tuple[str, ...] = RELEVANT_KEYWORDS) -> int:
    return sum(
        bool(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text, re.I)) for word in keywords
    )


def filter_candidates(articles: list[Article], limit: int) -> list[Article]:
    candidates = [
        article
        for article in articles
        if not any(phrase in article.title.casefold() for phrase in EXCLUDED_TITLE_PHRASES)
        and keyword_hits(article.title + " " + article.description) > 0
    ]
    # Round-robin the two broad categories to prevent a busy aviation feed starving tech.
    queues = {
        category: sorted(
            (article for article in candidates if article.category == category),
            key=lambda article: (
                -keyword_hits(article.title + " " + article.description),
                article.priority,
                -article.published_at.timestamp(),
                article.id,
            ),
        )
        for category in ("aviation", "technology")
    }
    result = []
    while len(result) < limit and any(queues.values()):
        for queue in queues.values():
            if queue and len(result) < limit:
                result.append(queue.pop(0))
    return result
