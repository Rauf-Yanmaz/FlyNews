from datetime import UTC, datetime

import pytest

from src.demo import demo_articles
from src.utils import fingerprint


@pytest.fixture
def now():
    return datetime(2026, 10, 7, 5, 0, tzinfo=UTC)


@pytest.fixture
def article(now):
    return demo_articles(now)[0]


@pytest.fixture
def southwest_stories(article):
    """The three differently worded factual analyses from the user's preview."""
    reports = [
        (
            "Southwest becomes first US airline with ChatGPT flight shopping",
            "Southwest, ChatGPT üzerinden doğrudan uçuş rezervasyonu sunan ilk ABD havayolu oldu",
            "Southwest Airlines, müşterilerinin ChatGPT arayüzü üzerinden doğrudan uçuş araması "
            "ve rezervasyon yapmasına olanak tanıyan bir entegrasyon başlattı.",
        ),
        (
            "A new plugin lets ChatGPT customers search Southwest flights",
            "Southwest Airlines uçuş arama ve rezervasyon için ChatGPT eklentisini başlattı",
            "Southwest Airlines, müşterilerin uçuş aramalarını ve rezervasyon süreçlerini "
            "kolaylaştırmak amacıyla ChatGPT tabanlı bir eklenti geliştirdiğini duyurdu.",
        ),
        (
            "Southwest's conversational commerce channel debuts in ChatGPT",
            "Southwest Airlines ChatGPT eklentisi yeni bir yapay zeka satış kanalı açıyor",
            "Southwest Airlines'ın ChatGPT eklentisi, uçuş alışverişi sürecini yapay zeka ile "
            "optimize ederek müşterilere daha kişiselleştirilmiş bir satın alma deneyimi "
            "sunmayı hedefliyor.",
        ),
    ]
    stories = []
    for index, (title, title_tr, summary) in enumerate(reports):
        story = article.model_copy(deep=True)
        story.id = f"southwest-{index}"
        story.title = title
        story.url = f"https://example.com/southwest-{index}"
        story.hash = fingerprint(story.url)
        story.analysis.article_id = story.id
        story.analysis.title_tr = title_tr
        story.analysis.summary = summary
        stories.append(story)
    return stories
