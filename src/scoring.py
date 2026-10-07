"""Deterministic ranking with light diversity among similarly strong stories."""

from src.config import Config, Weights
from src.models import Article, Scores


def calculate_score(scores: Scores, weights: Weights) -> float:
    return sum(getattr(scores, name) * weight for name, weight in weights.model_dump().items())


def select_top(articles: list[Article], config: Config) -> list[Article]:
    eligible = []
    for article in articles:
        article.selected = False
        if article.analysis is None:
            continue
        article.final_score = calculate_score(article.analysis.scores, config.weights)
        if (
            article.analysis.relevant
            and article.analysis.scores.ajet_relevance >= config.min_relevance_score
            and article.final_score >= config.min_final_score
        ):
            eligible.append(article)
    eligible.sort(
        key=lambda article: (
            -(article.final_score or 0),
            article.priority,
            -article.published_at.timestamp(),
            article.id,
        )
    )
    selected = []
    categories: set[str] = set()
    while eligible and len(selected) < config.max_daily_articles:
        best_score = eligible[0].final_score or 0
        index = next(
            (
                index
                for index, article in enumerate(eligible)
                if article.analysis.category not in categories
                and best_score - (article.final_score or 0) <= config.diversity_score_gap
            ),
            0,
        )
        article = eligible.pop(index)
        article.selected = True
        selected.append(article)
        categories.add(article.analysis.category)
    return selected
