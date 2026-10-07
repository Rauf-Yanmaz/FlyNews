"""Environment configuration; no secrets or model name embedded in application logic."""

import os
import re
from pathlib import Path
from typing import Self

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr, model_validator

ROOT = Path(__file__).resolve().parent.parent


class Weights(BaseModel):
    ajet_relevance: float = Field(default=0.35, ge=0, le=1)
    business_impact: float = Field(default=0.25, ge=0, le=1)
    novelty: float = Field(default=0.15, ge=0, le=1)
    feasibility: float = Field(default=0.15, ge=0, le=1)
    urgency: float = Field(default=0.10, ge=0, le=1)

    @model_validator(mode="after")
    def sum_to_one(self) -> Self:
        if abs(sum(self.model_dump().values()) - 1) > 1e-6:
            raise ValueError("Scoring weights must sum to 1")
        return self


class Config(BaseModel):
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""
    news_lookback_hours: int = Field(default=24, ge=1, le=168)
    max_articles_for_ai: int = Field(default=40, ge=1, le=200)
    max_daily_articles: int = Field(default=8, ge=1, le=10)
    min_relevance_score: int = Field(default=6, ge=1, le=10)
    min_final_score: float = Field(default=6.5, ge=1, le=10)
    ai_batch_size: int = Field(default=8, ge=1, le=10)
    ai_batch_delay_seconds: float = Field(default=15, ge=0, le=60)
    http_timeout_seconds: float = Field(default=30, gt=0, le=120)
    gemini_timeout_seconds: float = Field(default=60, gt=0, le=120)
    request_attempts: int = Field(default=3, ge=1, le=5)
    max_retry_delay_seconds: float = Field(default=60, ge=1, le=60)
    dedup_similarity: float = Field(default=0.86, ge=0.5, le=1)
    diversity_score_gap: float = Field(default=0.6, ge=0, le=2)
    state_retention_days: int = Field(default=30, ge=7, le=365)
    max_feed_entries: int = Field(default=200, ge=1, le=2000)
    database_path: str = str(ROOT / "data" / "news.db")
    dry_run: bool = False
    weights: Weights = Field(default_factory=Weights)

    @classmethod
    def from_env(cls) -> Self:
        load_dotenv(ROOT / ".env", override=False)
        values = {
            name: os.environ[name.upper()]
            for name in cls.model_fields
            if name != "weights" and name.upper() in os.environ
        }
        values["weights"] = Weights(
            **{
                name: os.environ[f"WEIGHT_{name.upper()}"]
                for name in Weights.model_fields
                if f"WEIGHT_{name.upper()}" in os.environ
            }
        )
        return cls.model_validate(values)

    def validate_credentials(self) -> None:
        missing = []
        if not self.gemini_api_key.get_secret_value().strip():
            missing.append("GEMINI_API_KEY")
        if not self.gemini_model.strip():
            missing.append("GEMINI_MODEL")
        elif not re.fullmatch(r"[A-Za-z0-9._-]+", self.gemini_model):
            raise ValueError("GEMINI_MODEL must be a model identifier")
        if not self.dry_run:
            if not self.telegram_bot_token.get_secret_value().strip():
                missing.append("TELEGRAM_BOT_TOKEN")
            if not self.telegram_chat_id.strip():
                missing.append("TELEGRAM_CHAT_ID")
        if missing:
            raise ValueError("Missing configuration: " + ", ".join(missing))
