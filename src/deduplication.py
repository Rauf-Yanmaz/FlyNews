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
    "jeppesen",
    "almatar",
)

# Require a named organization, a specific product, an event and a use context.
# Generic mentions of AI or the same airline are never enough to merge stories.
EVENT_PRODUCTS = ("chatgpt", "copilot", "gemini", "airflow", "foreflight")
EVENT_CONTEXTS = {
    "flight-shopping": r"\b(?:booking|shopping|search|retail|rezerv|arama|alışveriş|satış)\w*",
    "operations": r"\b(?:disruption|operations|aksaklık|operasyon)\w*",
}
LAUNCH = r"\b(?:launch|introduc|unveil|başlat|tanıt|geliştir|duyur|açıyor|açtı)\w*"
OTHER_EVENTS = (
    r"\b(?:cancel|discontinu|withdraw|outage|breach|iptal|sonlandır|kaldır|kesinti|sızıntı)\w*"
)
EARLY_STAGE = r"\b(?:pilot|trial|planned|plans|planlıyor|planlanan|yakında|deneme)\w*"
EVENT_FEATURES = {
    "refund": r"\b(?:refund|iade)\w*",
    "baggage": r"\b(?:baggage|bagaj)\w*",
    "loyalty": r"\b(?:loyalty|points|sadakat|puan)\w*",
    "check-in": r"\b(?:check in|checkin)\w*",
}


def named_entities(value: str, names: tuple[str, ...] = ENTITIES) -> set[str]:
    return {name for name in names if re.search(r"\b" + re.escape(name) + r"\b", value)}


def same_analyzed_event(first: Article, second: Article) -> bool:
    """Cluster short, differently worded reports only with several concrete signals."""
    if first.analysis is None or second.analysis is None:
        return False
    if abs((first.published_at - second.published_at).total_seconds()) > 36 * 3600:
        return False
    facts = [
        normalize_title(article.analysis.title_tr + " " + article.analysis.summary)
        for article in (first, second)
    ]
    actors = [named_entities(value) for value in facts]
    products = [named_entities(value, EVENT_PRODUCTS) for value in facts]
    if not actors[0] or actors[0] != actors[1] or not products[0] or products[0] != products[1]:
        return False
    # Preserve different dated/numbered announcements and different rollout stages.
    headlines = [
        normalize_title(item.title + " " + item.analysis.title_tr) for item in (first, second)
    ]
    if set(re.findall(r"\d+", headlines[0])) != set(re.findall(r"\d+", headlines[1])):
        return False
    if any(re.search(OTHER_EVENTS, value) or not re.search(LAUNCH, value) for value in facts):
        return False
    if bool(re.search(EARLY_STAGE, facts[0])) != bool(re.search(EARLY_STAGE, facts[1])):
        return False
    features = [
        {name for name, pattern in EVENT_FEATURES.items() if re.search(pattern, value)}
        for value in facts
    ]
    if features[0] != features[1]:
        return False
    contexts = [
        {name for name, pattern in EVENT_CONTEXTS.items() if re.search(pattern, value)}
        for value in facts
    ]
    return bool(contexts[0]) and contexts[0] == contexts[1]


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
    left_entities, right_entities = named_entities(left), named_entities(right)
    if left_entities and right_entities and left_entities != right_entities:
        return False
    if set(re.findall(r"\d+", left)) != set(re.findall(r"\d+", right)):
        return False
    shared = len(set(left.split()) & set(right.split()))
    overlap = shared / min(len(set(left.split())), len(set(right.split())))
    return overlap >= 0.65 and SequenceMatcher(None, left, right).ratio() >= threshold


def same_story(first: Article, second: Article, threshold: float = 0.86) -> bool:
    return (
        first.url == second.url
        or titles_similar(first.title, second.title, threshold)
        or same_analyzed_event(first, second)
    )


def deduplicate(articles: list[Article], threshold: float = 0.86) -> list[Article]:
    ordered = sorted(
        articles,
        key=lambda article: (
            article.analysis is not None and not article.analysis.relevant,
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
            representative.secondary_sources = list(
                dict.fromkeys(
                    representative.secondary_sources + [article.url] + article.secondary_sources
                )
            )
    return representatives
