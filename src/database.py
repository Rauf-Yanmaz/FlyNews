"""SQLite history and a small durable Telegram outbox."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from src.formatter import DigestMessage
from src.models import Article
from src.utils import fingerprint, utc_now


class StateError(RuntimeError):
    pass


class Database:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.row_factory = sqlite3.Row
        # DELETE journaling keeps the single-file cache portable; FULL sync checkpoints sends.
        self.connection.execute("PRAGMA synchronous = FULL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY, url TEXT NOT NULL, url_hash TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL, source TEXT NOT NULL, published_at TEXT NOT NULL,
                collected_at TEXT NOT NULL, processed_at TEXT NOT NULL,
                final_score REAL, selected INTEGER NOT NULL DEFAULT 0,
                telegram_sent_at TEXT, payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS articles_published ON articles(published_at);
            CREATE TABLE IF NOT EXISTS outbox (
                id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, text TEXT NOT NULL,
                article_ids TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending', 'sending', 'sent', 'uncertain')),
                message_id INTEGER, created_at TEXT NOT NULL, sent_at TEXT
            );
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *args: object) -> None:
        self.connection.close()

    def bind_channel(self, chat_id: str) -> None:
        row = self.connection.execute("SELECT value FROM metadata WHERE key='chat_id'").fetchone()
        if row and row["value"] != chat_id:
            raise StateError("Channel differs from saved state; use a separate DATABASE_PATH")
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO metadata(key,value) VALUES('chat_id',?)",
                (chat_id,),
            )

    def save_articles(self, articles: list[Article], now: datetime) -> None:
        with self.connection:
            for article in articles:
                self.connection.execute(
                    """
                    INSERT INTO articles(id,url,url_hash,title,source,published_at,collected_at,
                        processed_at,final_score,selected,payload)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET final_score=excluded.final_score,
                        selected=excluded.selected,payload=excluded.payload,
                        processed_at=excluded.processed_at
                """,
                    (
                        article.id,
                        article.url,
                        article.hash,
                        article.title,
                        article.source,
                        article.published_at.isoformat(),
                        article.collected_at.isoformat(),
                        now.isoformat(),
                        article.final_score,
                        int(article.selected),
                        article.model_dump_json(),
                    ),
                )

    def history(self, now: datetime, days: int) -> list[tuple[Article, bool]]:
        cutoff = (now - timedelta(days=days)).isoformat()
        rows = self.connection.execute(
            "SELECT payload,telegram_sent_at FROM articles WHERE published_at >= ?",
            (cutoff,),
        )
        return [
            (Article.model_validate_json(row["payload"]), row["telegram_sent_at"] is not None)
            for row in rows
        ]

    def enqueue(self, messages: list[DigestMessage], chat_id: str, now: datetime) -> None:
        with self.connection:
            for message in messages:
                identifier = fingerprint(chat_id + "\n" + message.text)
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO outbox(id,chat_id,text,article_ids,created_at)
                    VALUES(?,?,?,?,?)
                """,
                    (
                        identifier,
                        chat_id,
                        message.text,
                        json.dumps(message.article_ids),
                        now.isoformat(),
                    ),
                )

    def pending_messages(self) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM outbox WHERE status != 'sent' ORDER BY created_at,rowid",
            )
        )

    def set_status(self, identifier: str, status: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE outbox SET status=? WHERE id=?", (status, identifier))

    def mark_sent(self, identifier: str, message_id: int | None) -> None:
        now = utc_now().isoformat()
        with self.connection:
            row = self.connection.execute(
                "SELECT article_ids FROM outbox WHERE id=?",
                (identifier,),
            ).fetchone()
            if row is None:
                raise StateError("Unknown outbox message ID")
            self.connection.execute(
                "UPDATE outbox SET status='sent',message_id=?,sent_at=? WHERE id=?",
                (message_id, now, identifier),
            )
            for article_id in json.loads(row["article_ids"]):
                self.connection.execute(
                    "UPDATE articles SET telegram_sent_at=? WHERE id=?",
                    (now, article_id),
                )

    def resolve(self, identifier: str, resolution: str, message_id: int | None = None) -> None:
        row = self.connection.execute(
            "SELECT status FROM outbox WHERE id=?", (identifier,)
        ).fetchone()
        if not row or row["status"] not in {"sending", "uncertain"}:
            raise StateError("Only an ambiguous outbox message can be resolved")
        if resolution == "sent":
            self.mark_sent(identifier, message_id)
        elif resolution == "retry":
            self.set_status(identifier, "pending")
        else:
            raise StateError("Resolution must be sent or retry")

    def prune(self, now: datetime, days: int) -> None:
        cutoff = (now - timedelta(days=days)).isoformat()
        with self.connection:
            # Retain articles for any unfinished digest, even when older than the normal history.
            held_ids = {
                identifier
                for row in self.pending_messages()
                for identifier in json.loads(row["article_ids"])
            }
            rows = self.connection.execute(
                "SELECT id FROM articles WHERE published_at < ?", (cutoff,)
            )
            for row in list(rows):
                if row["id"] not in held_ids:
                    self.connection.execute("DELETE FROM articles WHERE id=?", (row["id"],))
            self.connection.execute(
                "DELETE FROM outbox WHERE status='sent' AND created_at < ?",
                (cutoff,),
            )
