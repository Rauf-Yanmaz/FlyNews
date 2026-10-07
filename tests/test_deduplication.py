from src.deduplication import deduplicate, normalize_title, titles_similar


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
