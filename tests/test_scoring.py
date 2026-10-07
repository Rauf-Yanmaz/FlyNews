import pytest
from pydantic import ValidationError

from src.config import Config, Weights
from src.models import Scores
from src.scoring import calculate_score, select_top


def test_weighted_score():
    scores = Scores(ajet_relevance=9, business_impact=8, novelty=7, feasibility=7, urgency=5)
    assert calculate_score(scores, Weights()) == pytest.approx(7.75)
    with pytest.raises(ValidationError):
        Weights(ajet_relevance=0.5)


def test_thresholds_do_not_fill_with_weak_items(article):
    weak = article.model_copy(deep=True)
    weak.id = "weak"
    weak.analysis.scores.ajet_relevance = 5
    irrelevant = article.model_copy(deep=True)
    irrelevant.id = "irrelevant"
    irrelevant.analysis.relevant = False
    assert select_top([article, weak, irrelevant], Config(max_daily_articles=8)) == [article]


def test_diversity_only_among_similarly_strong_stories(article):
    best = article.model_copy(deep=True)
    best.id = "best"
    best.analysis.scores = Scores(
        ajet_relevance=10, business_impact=10, novelty=9, feasibility=9, urgency=8
    )
    same_category = best.model_copy(deep=True)
    same_category.id = "same"
    same_category.analysis.scores.urgency = 7
    diverse = best.model_copy(deep=True)
    diverse.id = "diverse"
    diverse.analysis.category = "AI"
    diverse.analysis.scores.ajet_relevance = 9
    assert [
        item.id for item in select_top([same_category, diverse, best], Config(max_daily_articles=2))
    ] == ["best", "diverse"]
    diverse.analysis.scores.ajet_relevance = 6
    assert [
        item.id for item in select_top([same_category, diverse, best], Config(max_daily_articles=2))
    ] == ["best", "same"]
