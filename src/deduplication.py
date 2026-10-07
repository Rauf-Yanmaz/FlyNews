"""Conservative event clustering with preferred-source representatives."""

import re
import unicodedata
from difflib import SequenceMatcher

from src.models import Article

STOP_WORDS = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "at"}
ENTITIES = (
    "ajet",
    "pegasus",
    "turkish airlines",
    "ryanair",
    "easyjet",
    "wizz air",
    "lufthansa",
    "eurowings",
    "air france",
    "klm",
    "british airways",
    "iberia",
    "vueling",
    "jetblue",
    "southwest",
    "delta",
    "united",
    "emirates",
    "qatar airways",
    "singapore airlines",
    "airbus",
    "boeing",
    "openai",
    "google",
    "microsoft",
    "anthropic",
    "nvidia",
)


def normalize_title(title: str) -> str:
    # Keep clauses after dashes: they may distinguish otherwise identical events.
    words = re.findall(r"\w+", unicodedata.normalize("NFKC", title).casefold())
    return " ".join(word for word in words if word not in STOP_WORDS)


def titles_similar(first: str, second: str, threshold: float = 0.86) -> bool:
    left, right = normalize_title(first), normalize_title(second)
    if not left or not right:
        return False
    if left == right:
        return True
    if min(len(left.split()), len(right.split())) < 4:
        return False

    # Prevent merging equivalent announcements by different named companies or numbers.
    def entities(value: str) -> set[str]:
        return {name for name in ENTITIES if re.search(r"\b" + re.escape(name) + r"\b", value)}

    left_entities, right_entities = entities(left), entities(right)
    if left_entities and right_entities and left_entities != right_entities:
        return False
    if set(re.findall(r"\d+", left)) != set(re.findall(r"\d+", right)):
        return False
    shared = len(set(left.split()) & set(right.split()))
    overlap = shared / min(len(set(left.split())), len(set(right.split())))
    return overlap >= 0.65 and SequenceMatcher(None, left, right).ratio() >= threshold


def same_story(first: Article, second: Article, threshold: float = 0.86) -> bool:
    return first.url == second.url or titles_similar(first.title, second.title, threshold)


def deduplicate(articles: list[Article], threshold: float = 0.86) -> list[Article]:
    ordered = sorted(
        articles,
        key=lambda article: (
            article.priority,
            -len(article.description),
            -article.published_at.timestamp(),
            -len(article.title),
            article.id,
        ),
    )
    representatives: list[Article] = []
    for article in ordered:
        representative = next(
            (item for item in representatives if same_story(item, article, threshold)), None
        )
        if representative is None:
            representatives.append(article.model_copy(deep=True))
        elif article.url != representative.url:
            representative.secondary_sources.append(article.url)
    return representatives
