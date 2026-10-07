"""Normalized articles and strictly validated Gemini output."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.utils import normalize_url

AICategory = Literal[
    "Aviation",
    "AI",
    "Customer Experience",
    "Operations",
    "Commercial",
    "Airport / Infrastructure",
    "Regulation / Sustainability",
    "Cybersecurity / Data",
]
Score = Annotated[int, Field(strict=True, ge=1, le=10)]


class NewsSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    url: str
    category: Literal["aviation", "technology"]
    priority: int = Field(default=2, ge=1, le=10)  # Lower is better.

    _valid_url = field_validator("url")(normalize_url)


class Scores(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ajet_relevance: Score
    business_impact: Score
    novelty: Score
    feasibility: Score
    urgency: Score


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    article_id: str = Field(min_length=1, max_length=64)
    relevant: bool
    category: AICategory
    title_tr: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=450)
    why_it_matters_for_ajet: str = Field(min_length=1, max_length=350)
    possible_ajet_use_case: str = Field(min_length=1, max_length=350)
    affected_teams: list[Annotated[str, Field(min_length=1, max_length=32)]] = Field(
        min_length=1, max_length=5
    )
    scores: Scores


class Article(BaseModel):
    id: str
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=3000)
    url: str
    source: str = Field(min_length=1, max_length=120)
    feed_name: str
    category: Literal["aviation", "technology"]
    priority: int = 2
    published_at: datetime
    collected_at: datetime
    hash: str
    secondary_sources: list[str] = Field(default_factory=list)
    analysis: Analysis | None = None
    final_score: float | None = None
    selected: bool = False

    _valid_url = field_validator("url")(normalize_url)

    @field_validator("published_at", "collected_at")
    @classmethod
    def aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Timestamp must have a timezone")
        return value.astimezone(UTC)
