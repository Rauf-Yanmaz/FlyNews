from datetime import timedelta

import pytest

from src.deduplication import deduplicate, normalize_title, same_story, titles_similar


def test_title_normalization():
    assert normalize_title("The Airline: New AI, for Operations!") == "airline new ai operations"


def test_cluster_prefers_priority_and_retains_secondary(article):
    title = "Ryanair introduces AI support for disruption management"
    first = article.model_copy(update={"title": title, "priority": 3})
    second = article.model_copy(
        update={
            "id": "second",
            "title": title.lower(),
            "priority": 1,
            "url": "https://example.com/second",
        }
    )
    result = deduplicate([first, second])
    assert len(result) == 1
    assert result[0].id == "second"
    assert result[0].secondary_sources == [first.url]


def test_distinct_companies_numbers_and_short_titles_are_not_merged():
    assert not titles_similar(
        "Ryanair launches new AI customer support system",
        "easyJet launches new AI customer support system",
    )
    assert not titles_similar(
        "Airline orders 20 aircraft for fleet renewal",
        "Airline orders 30 aircraft for fleet renewal",
    )
    assert not titles_similar("AI pilot", "AI pilots")
    assert titles_similar(
        "Airline introduces new biometric boarding pilot",
        "Airline introduced new biometric boarding pilot",
    )


def test_dash_clauses_that_distinguish_events_are_preserved():
    assert not titles_similar(
        "Airline expansion plans — Ryanair orders 20 aircraft",
        "Airline expansion plans — easyJet orders 30 aircraft",
    )


def test_preview_paraphrases_merge_after_analysis_with_all_sources(southwest_stories):
    first, second, third = southwest_stories
    assert not titles_similar(first.title, second.title)
    assert not titles_similar(first.title, third.title)
    result = deduplicate(southwest_stories)
    assert len(result) == 1
    assert {result[0].url, *result[0].secondary_sources} == {
        story.url for story in southwest_stories
    }


@pytest.mark.parametrize(
    "title_tr,summary",
    [
        ("Ryanair ChatGPT uçuş aramasını başlattı", "Ryanair uçuş araması için ChatGPT başlattı."),
        (
            "Southwest Gemini uçuş aramasını başlattı",
            "Southwest uçuş araması için Gemini başlattı.",
        ),
        ("Southwest ChatGPT desteğini kaldırdı", "Southwest uçuş araması eklentisini sonlandırdı."),
        (
            "Southwest ChatGPT operasyon araçlarını tanıttı",
            "Southwest aksaklık yönetimini başlattı.",
        ),
        (
            "Southwest ChatGPT uçuş arama pilotunu başlattı",
            "Southwest deneme uygulamasını tanıttı.",
        ),
        (
            "Southwest ChatGPT rezervasyon iadelerini başlattı",
            "Southwest yeni iade özelliğini tanıttı.",
        ),
        ("Southwest ChatGPT 2 eklentisini başlattı", "Southwest uçuş aramasını başlattı."),
    ],
)
def test_related_but_distinct_events_are_preserved(southwest_stories, title_tr, summary):
    first, second, _ = southwest_stories
    second.analysis.title_tr = title_tr
    second.analysis.summary = summary
    assert not same_story(first, second)


def test_event_matching_needs_analysis_and_recent_dates(southwest_stories):
    first, second, _ = southwest_stories
    second.published_at -= timedelta(days=3)
    assert not same_story(first, second)
    second.published_at = first.published_at
    second.analysis = None
    assert not same_story(first, second)


def test_irrelevant_representative_does_not_hide_relevant_report(southwest_stories):
    first, second, _ = southwest_stories
    first.priority = 1
    first.analysis.relevant = False
    second.priority = 3
    assert deduplicate([first, second])[0].id == second.id
