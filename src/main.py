"""CLI entry point for the once-daily job."""

import argparse
import fcntl
import json
import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import requests
from pydantic import ValidationError

from src.ai_analyzer import AnalysisError, GeminiAnalyzer
from src.collector import CollectionError, collect_articles
from src.config import Config
from src.database import Database, StateError
from src.deduplication import deduplicate, same_story
from src.feeds import SOURCES
from src.filters import filter_candidates, filter_recent
from src.formatter import format_digest
from src.scoring import select_top
from src.telegram_publisher import PublishError, TelegramPublisher
from src.utils import utc_now

logger = logging.getLogger(__name__)


@contextmanager
def state_lock(path: str) -> Iterator[None]:
    """Local macOS/Linux protection in addition to Actions workflow concurrency."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path + ".lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise StateError("Another process is using this database") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def run_pipeline(config: Config) -> int:
    config.validate_credentials()
    now = utc_now()
    with Database(":memory:" if config.dry_run else config.database_path) as database:
        with requests.Session() as session:
            if not config.dry_run:
                database.bind_channel(config.telegram_chat_id)
                if database.pending_messages():
                    count = TelegramPublisher(config, session).publish_pending(database)
                    logger.info("Recovered earlier digest: %d messages published", count)
                    return 0
            articles = collect_articles(SOURCES, config, now)
            articles = filter_recent(articles, now, config.news_lookback_hours)
            logger.info(
                "%d remained after %dh filtering", len(articles), config.news_lookback_hours
            )
            articles = deduplicate(articles, config.dedup_similarity)
            logger.info("%d remained after deduplication", len(articles))
            history = database.history(now, config.state_retention_days)
            candidates = []
            for article in articles:
                matches = [
                    (item, sent)
                    for item, sent in history
                    if same_story(article, item, config.dedup_similarity)
                ]
                if any(sent for _, sent in matches):
                    continue
                if matches:
                    cached, _ = matches[0]
                    if filter_recent([cached], now, config.news_lookback_hours):
                        candidates.append(cached)
                else:
                    candidates.append(article)
            # Two new headlines may map to the same historical representative.
            candidates = deduplicate(candidates, config.dedup_similarity)
            candidates = filter_candidates(candidates, config.max_articles_for_ai)
            cached = [article for article in candidates if article.analysis is not None]
            fresh = [article for article in candidates if article.analysis is None]
            logger.info("%d sent to AI analysis; %d reused from history", len(fresh), len(cached))
            analyzed = GeminiAnalyzer(config, session).analyze(fresh) if fresh else []
            if fresh and not analyzed and not cached:
                raise AnalysisError(
                    "No candidate received a valid AI analysis; check Gemini settings"
                )
            analyzed += cached
            selected = select_top(analyzed, config)
            logger.info("%d articles selected", len(selected))
            messages = format_digest(selected, now)
            if config.dry_run:
                for index, message in enumerate(messages, 1):
                    print(
                        f"\n--- Telegram preview {index}/{len(messages)} (HTML) ---\n{message.text}"
                    )
                if not messages:
                    logger.info("No qualifying stories; no digest to publish")
                return 0
            database.save_articles(analyzed, now)
            database.prune(now, config.state_retention_days)
            if not messages:
                logger.info("No qualifying stories; no Telegram message sent")
                return 0
            database.enqueue(messages, config.telegram_chat_id, now)
            count = TelegramPublisher(config, session).publish_pending(database)
            logger.info("Telegram digest published successfully: %d messages", count)
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # HTTP debug output can include token-bearing Telegram URLs.
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)
    parser = argparse.ArgumentParser(description="AJet daily aviation and technology intelligence")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview HTML; do not send or change state"
    )
    parser.add_argument("--hours", type=int, help="Lookback hours (1..168)")
    parser.add_argument("--limit", type=int, help="Maximum selected items (1..10)")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--demo", action="store_true", help="Offline fictional preview; requires --dry-run"
    )
    actions.add_argument(
        "--outbox-status", action="store_true", help="Inspect unfinished message state"
    )
    actions.add_argument("--resolve-message", metavar="ID", help="Reconcile an ambiguous delivery")
    parser.add_argument("--resolution", choices=("sent", "retry"))
    parser.add_argument("--telegram-message-id", type=int)
    args = parser.parse_args(argv)
    if args.demo and not args.dry_run:
        parser.error("--demo requires --dry-run")
    if bool(args.resolve_message) != bool(args.resolution):
        parser.error("--resolve-message and --resolution must be used together")
    if args.telegram_message_id is not None and args.resolution != "sent":
        parser.error("--telegram-message-id requires --resolution sent")
    if args.dry_run and (args.outbox_status or args.resolve_message):
        parser.error("Outbox maintenance cannot be combined with --dry-run")
    try:
        config = Config.from_env()
        overrides = {}
        if args.dry_run:
            overrides["dry_run"] = True
        if args.hours is not None:
            overrides["news_lookback_hours"] = args.hours
        if args.limit is not None:
            overrides["max_daily_articles"] = args.limit
        config = Config.model_validate(config.model_dump() | overrides)
        if args.demo:
            from src.demo import demo_articles

            now = utc_now()
            for message in format_digest(select_top(demo_articles(now), config), now, demo=True):
                print(message.text)
            return 0
        if args.outbox_status or args.resolve_message:
            with state_lock(config.database_path), Database(config.database_path) as database:
                if args.outbox_status:
                    print(
                        json.dumps(
                            [dict(row) for row in database.pending_messages()],
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                else:
                    database.resolve(
                        args.resolve_message, args.resolution, args.telegram_message_id
                    )
                    logger.info("Outbox message reconciled")
            return 0
        if config.dry_run:
            return run_pipeline(config)
        with state_lock(config.database_path):
            return run_pipeline(config)
    except ValidationError as error:
        # Pydantic's default error text includes inputs. Log only field locations.
        fields = {".".join(str(part) for part in issue["loc"]) for issue in error.errors()}
        logger.error("Invalid configuration or data fields: %s", ", ".join(sorted(fields)))
    except (ValueError, CollectionError, AnalysisError, PublishError, StateError) as error:
        logger.error("%s", error)
    except (sqlite3.Error, OSError):
        logger.error("Database or filesystem operation failed; check state access")
    except Exception as error:
        logger.error(
            "Unexpected failure (%s); no credentials or raw responses logged", type(error).__name__
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
