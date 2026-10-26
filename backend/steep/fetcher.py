"""Polls feeds, stores new and changed articles, and pulls full text for truncated feeds."""

from __future__ import annotations

import asyncio
import calendar
import hashlib
import logging
import sqlite3
import weakref
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser
import httpx
import trafilatura

from . import db
from .config import get_settings
from .content import clean_url, content_hash, first_image, make_excerpt, sanitize, text_of
from .events import broadcaster

log = logging.getLogger("steep.fetcher")

USER_AGENT = "Mozilla/5.0 (compatible; Steep/0.1; self-hosted RSS reader)"
# Below this many characters of body text, a feed item is treated as a teaser and we fetch the page.
FULLTEXT_THRESHOLD = 600
MAX_ENTRIES_PER_FETCH = 200
MAX_BACKOFF = timedelta(hours=24)

_client: httpx.AsyncClient | None = None
# Per-event-loop so tests (and restarts) never reuse a lock bound to a closed loop.
_feed_locks: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[int, asyncio.Lock]]" = weakref.WeakKeyDictionary()


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        s = get_settings()
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(s.fetch_timeout, connect=10),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            limits=httpx.Limits(max_connections=s.fetch_concurrency * 2),
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


# ---------------------------------------------------------------- parsing helpers


def _entry_time(entry: Any) -> str | None:
    now = db.utcnow()
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        t = entry.get(key)
        if t:
            try:
                dt = datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
            except (OverflowError, ValueError, TypeError, OSError):
                continue
            # Some feeds post-date items; never let them float above everything else.
            return db.iso(min(dt, now))
    return None


def _entry_guid(entry: Any) -> str:
    for key in ("id", "guid", "link"):
        v = entry.get(key)
        if v:
            return str(v)[:1000]
    basis = (entry.get("title") or "") + (entry.get("summary") or "")
    return "sha1:" + hashlib.sha1(basis.encode("utf-8")).hexdigest()


def _entry_link(entry: Any, base: str | None) -> str | None:
    link = entry.get("feedburner_origlink") or entry.get("link")
    if not link:
        for l in entry.get("links", []) or []:
            if l.get("rel") in (None, "alternate") and l.get("href"):
                link = l["href"]
                break
    if link and base and not link.startswith(("http://", "https://")):
        from urllib.parse import urljoin

        link = urljoin(base, link)
    return clean_url(link)


def _entry_image(entry: Any, html: str | None) -> str | None:
    for key in ("media_thumbnail", "media_content"):
        for m in entry.get(key, []) or []:
            url = m.get("url")
            medium = m.get("medium") or ""
            mtype = m.get("type") or ""
            if url and (key == "media_thumbnail" or medium == "image" or mtype.startswith("image/")):
                return url
    for enc in entry.get("enclosures", []) or []:
        if (enc.get("type") or "").startswith("image/") and enc.get("href"):
            return enc["href"]
    img = entry.get("image")
    if isinstance(img, dict) and img.get("href"):
        return img["href"]
    return first_image(html)


def _entry_html(entry: Any) -> tuple[str, str]:
    """Return (summary_html, content_html) as provided by the feed."""
    summary = entry.get("summary") or ""
    content = ""
    for c in entry.get("content", []) or []:
        value = c.get("value") or ""
        if len(value) > len(content):
            content = value
    return summary, content


# ---------------------------------------------------------------- full-text extraction


async def extract_fulltext(url: str) -> str | None:
    """Fetch the article page and pull out the main content as HTML (F-13)."""
    try:
        resp = await client().get(url, headers={"Accept": "text/html,application/xhtml+xml"})
    except httpx.HTTPError as exc:
        log.info("extract fetch failed %s: %s", url, exc)
        return None
    if resp.status_code >= 400 or "html" not in resp.headers.get("content-type", "html"):
        return None

    def run() -> str | None:
        return trafilatura.extract(
            resp.text,
            url=str(resp.url),
            output_format="html",
            include_images=True,
            include_links=True,
            include_comments=False,
            favor_precision=True,
        )

    try:
        html = await asyncio.to_thread(run)
    except Exception as exc:  # trafilatura can raise on odd markup
        log.info("extract parse failed %s: %s", url, exc)
        return None
    if not html or len(text_of(html)) < 200:
        return None
    return html


# ---------------------------------------------------------------- storing


def _refresh_minutes(feed: sqlite3.Row) -> int:
    s = get_settings()
    return max(s.min_refresh_minutes, feed["refresh_minutes"] or s.default_refresh_minutes)


def _schedule_next(conn: sqlite3.Connection, feed: sqlite3.Row, ok: bool, status: int | None, error: str | None) -> None:
    now = db.utcnow()
    minutes = _refresh_minutes(feed)
    if ok:
        conn.execute(
            "UPDATE feeds SET last_fetch_at=?, last_success_at=?, next_fetch_at=?, last_status=?, "
            "last_error=NULL, fail_count=0 WHERE id=?",
            (db.iso(now), db.iso(now), db.iso(now + timedelta(minutes=minutes)), status, feed["id"]),
        )
    else:
        fails = feed["fail_count"] + 1
        delay = min(timedelta(minutes=minutes * (2 ** min(fails, 6))), MAX_BACKOFF)
        conn.execute(
            "UPDATE feeds SET last_fetch_at=?, next_fetch_at=?, last_status=?, last_error=?, fail_count=? WHERE id=?",
            (db.iso(now), db.iso(now + delay), status, (error or "")[:500], fails, feed["id"]),
        )


def _fts_upsert(conn: sqlite3.Connection, article_id: int, title: str | None, html: str | None) -> None:
    conn.execute("DELETE FROM articles_fts WHERE rowid = ?", (article_id,))
    conn.execute(
        "INSERT INTO articles_fts(rowid, title, body) VALUES (?, ?, ?)",
        (article_id, title or "", text_of(html)[:200_000]),
    )


async def fetch_feed(feed_id: int) -> dict[str, Any]:
    """Fetch one feed. Returns a small report: {new, updated, error}."""
    locks = _feed_locks.setdefault(asyncio.get_running_loop(), {})
    lock = locks.setdefault(feed_id, asyncio.Lock())
    async with lock:
        return await _fetch_feed(feed_id)


async def _fetch_feed(feed_id: int) -> dict[str, Any]:
    with db.connect() as conn:
        feed = conn.execute("SELECT * FROM feeds WHERE id=? AND deleted_at IS NULL", (feed_id,)).fetchone()
    if feed is None:
        return {"new": 0, "updated": 0, "error": "missing"}

    headers = {"Accept": "application/rss+xml, application/atom+xml, application/feed+json, application/xml;q=0.9, */*;q=0.8"}
    if feed["etag"]:
        headers["If-None-Match"] = feed["etag"]
    if feed["last_modified"]:
        headers["If-Modified-Since"] = feed["last_modified"]

    try:
        resp = await client().get(feed["url"], headers=headers)
    except httpx.HTTPError as exc:
        with db.connect() as conn:
            _schedule_next(conn, feed, ok=False, status=None, error=f"{type(exc).__name__}: {exc}")
        return {"new": 0, "updated": 0, "error": str(exc)}

    if resp.status_code == 304:
        with db.connect() as conn:
            _schedule_next(conn, feed, ok=True, status=304, error=None)
        return {"new": 0, "updated": 0, "error": None}
    if resp.status_code >= 400:
        with db.connect() as conn:
            _schedule_next(conn, feed, ok=False, status=resp.status_code, error=f"HTTP {resp.status_code}")
        return {"new": 0, "updated": 0, "error": f"HTTP {resp.status_code}"}

    parsed = await asyncio.to_thread(feedparser.parse, resp.content, response_headers={k: v for k, v in resp.headers.items()})
    if not parsed.entries and parsed.get("bozo") and not parsed.get("version"):
        with db.connect() as conn:
            _schedule_next(conn, feed, ok=False, status=resp.status_code, error="Not a valid feed")
        return {"new": 0, "updated": 0, "error": "Not a valid feed"}

    site_url = parsed.feed.get("link") or feed["site_url"]
    entries = list(parsed.entries)[:MAX_ENTRIES_PER_FETCH]

    # Work out what is new or changed before touching the network for full text.
    with db.connect() as conn:
        updated_marks_unread = db.get_setting(conn, "updated_marks_unread") == "1"
        candidates = []
        for entry in entries:
            guid = _entry_guid(entry)
            if conn.execute("SELECT 1 FROM tombstones WHERE feed_id=? AND guid=?", (feed_id, guid)).fetchone():
                continue
            summary, content = _entry_html(entry)
            title = (entry.get("title") or "").strip() or None
            link = _entry_link(entry, site_url)
            h = content_hash(title, content or summary)
            existing = conn.execute(
                "SELECT id, content_hash, extracted, published_at FROM articles WHERE feed_id=? AND guid=?",
                (feed_id, guid),
            ).fetchone()
            if existing is None and link and title:
                dup = conn.execute(
                    "SELECT id FROM articles WHERE feed_id=? AND url=? AND title=?", (feed_id, link, title)
                ).fetchone()
                if dup:
                    continue
            if existing is not None and existing["content_hash"] == h:
                continue
            candidates.append((entry, guid, title, link, summary, content, h, existing))

    sem = asyncio.Semaphore(4)

    async def maybe_extract(link: str | None, summary: str, content: str) -> tuple[str | None, bool]:
        if not feed["fulltext"] or not link:
            return None, False
        if len(text_of(content or summary)) >= FULLTEXT_THRESHOLD:
            return None, False
        async with sem:
            html = await extract_fulltext(link)
        return html, html is None

    extracted = await asyncio.gather(*(maybe_extract(c[3], c[4], c[5]) for c in candidates))

    new_count = updated_count = 0
    now = db.iso()
    with db.connect() as conn, db.transaction(conn):
        if parsed.feed.get("title") and not feed["title"]:
            conn.execute("UPDATE feeds SET title=? WHERE id=?", (parsed.feed["title"].strip()[:300], feed_id))
        if site_url and site_url != feed["site_url"]:
            conn.execute("UPDATE feeds SET site_url=? WHERE id=?", (site_url, feed_id))
        if not feed["favicon_url"] and site_url:
            from urllib.parse import urlsplit

            host = urlsplit(site_url).netloc
            if host:
                conn.execute("UPDATE feeds SET favicon_url=? WHERE id=?", (f"https://{host}/favicon.ico", feed_id))

        for (entry, guid, title, link, summary, content, h, existing), (full, failed) in zip(candidates, extracted):
            body_html = full or content or summary
            clean_body = sanitize(body_html, link or site_url)
            clean_summary = sanitize(summary, link or site_url)
            excerpt = make_excerpt(summary, full or content, title)
            image = _entry_image(entry, content or summary or full)
            published = _entry_time(entry)
            author = (entry.get("author") or "").strip()[:200] or None

            if existing is None:
                cur = conn.execute(
                    "INSERT INTO articles(feed_id, guid, url, title, author, published_at, fetched_at, summary_html, "
                    "content_html, excerpt, image_url, content_hash, extracted, extract_failed) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (feed_id, guid, link, title, author, published or now, now, clean_summary, clean_body,
                     excerpt, image, h, 1 if full else 0, 1 if failed else 0),
                )
                _fts_upsert(conn, cur.lastrowid, title, clean_body)
                new_count += 1
            else:
                conn.execute(
                    "UPDATE articles SET url=?, title=?, author=?, summary_html=?, content_html=?, excerpt=?, "
                    "image_url=COALESCE(?, image_url), content_hash=?, extracted=?, extract_failed=?, updated_at=?"
                    + (", read_at=NULL" if updated_marks_unread else "")
                    + " WHERE id=?",
                    (link, title, author, clean_summary, clean_body, excerpt, image, h,
                     1 if full else 0, 1 if failed else 0, now, existing["id"]),
                )
                _fts_upsert(conn, existing["id"], title, clean_body)
                updated_count += 1

        conn.execute(
            "UPDATE feeds SET etag=?, last_modified=? WHERE id=?",
            (resp.headers.get("etag"), resp.headers.get("last-modified"), feed_id),
        )
        fresh = conn.execute("SELECT * FROM feeds WHERE id=?", (feed_id,)).fetchone()
        _schedule_next(conn, fresh, ok=True, status=resp.status_code, error=None)

    if new_count or updated_count:
        broadcaster.publish("articles", {"feed_id": feed_id, "new": new_count, "updated": updated_count})
    return {"new": new_count, "updated": updated_count, "error": None}


async def refresh(feed_ids: list[int]) -> dict[str, int]:
    sem = asyncio.Semaphore(get_settings().fetch_concurrency)

    async def one(fid: int) -> dict[str, Any]:
        async with sem:
            try:
                return await fetch_feed(fid)
            except Exception as exc:  # never let one feed kill the batch
                log.exception("feed %s failed", fid)
                return {"new": 0, "updated": 0, "error": str(exc)}

    results = await asyncio.gather(*(one(f) for f in feed_ids))
    totals = {"feeds": len(feed_ids), "new": sum(r["new"] for r in results),
              "updated": sum(r["updated"] for r in results), "errors": sum(1 for r in results if r["error"])}
    broadcaster.publish("sync", totals)
    return totals


async def refresh_due() -> dict[str, int]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id FROM feeds WHERE deleted_at IS NULL AND (next_fetch_at IS NULL OR next_fetch_at <= ?)",
            (db.iso(),),
        ).fetchall()
    ids = [r["id"] for r in rows]
    if not ids:
        return {"feeds": 0, "new": 0, "updated": 0, "errors": 0}
    return await refresh(ids)


def purge(conn: sqlite3.Connection) -> int:
    """Delete read, unsaved articles past the retention window; keep tombstones so they never return."""
    days = int(db.get_setting(conn, "retention_days") or 90)
    cutoff = db.iso(db.utcnow() - timedelta(days=days))
    now = db.iso()
    with db.transaction(conn):
        rows = conn.execute(
            "SELECT id, feed_id, guid FROM articles WHERE saved_at IS NULL AND read_at IS NOT NULL AND published_at < ?",
            (cutoff,),
        ).fetchall()
        for r in rows:
            conn.execute("INSERT OR IGNORE INTO tombstones(feed_id, guid, created_at) VALUES (?,?,?)",
                         (r["feed_id"], r["guid"], now))
            conn.execute("DELETE FROM articles_fts WHERE rowid=?", (r["id"],))
            conn.execute("DELETE FROM articles WHERE id=?", (r["id"],))
        # Feeds unsubscribed more than 10 minutes ago (past the undo window) go for good.
        gone = conn.execute(
            "SELECT id FROM feeds WHERE deleted_at IS NOT NULL AND deleted_at < ?",
            (db.iso(db.utcnow() - timedelta(minutes=10)),),
        ).fetchall()
        for g in gone:
            conn.execute("DELETE FROM articles_fts WHERE rowid IN (SELECT id FROM articles WHERE feed_id=?)", (g["id"],))
            conn.execute("DELETE FROM tombstones WHERE feed_id=?", (g["id"],))
            conn.execute("DELETE FROM feeds WHERE id=?", (g["id"],))
    return len(rows)
