from datetime import UTC, datetime

import pytest

from src.demo import demo_articles


@pytest.fixture
def now():
    return datetime(2026, 10, 7, 5, 0, tzinfo=UTC)


@pytest.fixture
def article(now):
    return demo_articles(now)[0]
