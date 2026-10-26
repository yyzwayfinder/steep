"""SQLite access: one short-lived connection per unit of work, WAL mode, versioned migrations."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import get_settings

MIGRATIONS: list[str] = [
    # 1 — initial schema
    """
    CREATE TABLE folders (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        sort_order INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE feeds (
        id INTEGER PRIMARY KEY,
        folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
        url TEXT NOT NULL UNIQUE,
        site_url TEXT,
        title TEXT,
        custom_title TEXT,
        favicon_url TEXT,
        refresh_minutes INTEGER,
        fulltext INTEGER NOT NULL DEFAULT 1,
        muted INTEGER NOT NULL DEFAULT 0,
        sort_order INTEGER NOT NULL DEFAULT 0,
        etag TEXT,
        last_modified TEXT,
        last_fetch_at TEXT,
        next_fetch_at TEXT,
        last_success_at TEXT,
        last_status INTEGER,
        last_error TEXT,
        fail_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        deleted_at TEXT
    );

    CREATE TABLE articles (
        id INTEGER PRIMARY KEY,
        feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
        guid TEXT NOT NULL,
        url TEXT,
        title TEXT,
        author TEXT,
        published_at TEXT NOT NULL,
        fetched_at TEXT NOT NULL,
        summary_html TEXT,
        content_html TEXT,
        excerpt TEXT,
        image_url TEXT,
        content_hash TEXT,
        extracted INTEGER NOT NULL DEFAULT 0,
        extract_failed INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT,
        read_at TEXT,
        saved_at TEXT,
        read_progress REAL,
        UNIQUE (feed_id, guid)
    );
    CREATE INDEX idx_articles_feed_time ON articles(feed_id, published_at DESC, id DESC);
    CREATE INDEX idx_articles_time ON articles(published_at DESC, id DESC);
    CREATE INDEX idx_articles_unread ON articles(read_at) WHERE read_at IS NULL;
    CREATE INDEX idx_articles_saved ON articles(saved_at) WHERE saved_at IS NOT NULL;
    CREATE INDEX idx_articles_url ON articles(feed_id, url);

    CREATE VIRTUAL TABLE articles_fts USING fts5(title, body, tokenize = 'unicode61 remove_diacritics 2');

    CREATE TABLE tombstones (
        feed_id INTEGER NOT NULL,
        guid TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (feed_id, guid)
    );

    CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = _connect(get_settings().db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def migrate() -> None:
    with connect() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for i, script in enumerate(MIGRATIONS[version:], start=version + 1):
            with transaction(conn):
                for stmt in _split(script):
                    conn.execute(stmt)
                conn.execute(f"PRAGMA user_version = {i}")


def _split(script: str) -> list[str]:
    """Split a migration into statements (no semicolons inside our SQL literals)."""
    return [s.strip() for s in script.split(";") if s.strip()]


DEFAULT_SETTINGS = {
    "retention_days": "90",
    "updated_marks_unread": "0",
    "resume_minutes": "60",
    "skip_reddit_on_import": "1",
}


def get_setting(conn: sqlite3.Connection, key: str) -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        return row["value"]
    return DEFAULT_SETTINGS.get(key, "")


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def all_settings(conn: sqlite3.Connection) -> dict[str, str]:
    out = dict(DEFAULT_SETTINGS)
    for row in conn.execute("SELECT key, value FROM settings"):
        out[row["key"]] = row["value"]
    return out
