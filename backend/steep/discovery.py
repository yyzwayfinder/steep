"""Find the feeds behind a website, YouTube channel or Mastodon profile URL (F-1, F-7)."""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from typing import Any
from urllib.parse import urljoin, urlsplit

import feedparser
import httpx
import lxml.html

from .fetcher import _entry_time, client

FEED_TYPES = {
    "application/rss+xml": "RSS",
    "application/atom+xml": "Atom",
    "application/feed+json": "JSON Feed",
    "application/json": "JSON Feed",
    "application/rdf+xml": "RSS",
    "application/xml": "RSS",
    "text/xml": "RSS",
}
COMMON_PATHS = ["/feed", "/rss", "/feed.xml", "/rss.xml", "/atom.xml", "/index.xml", "/feed/", "/rss/"]
MAX_CANDIDATES = 6


class DiscoveryError(Exception):
    pass


def normalize(url: str) -> str:
    url = url.strip()
    if not url:
        raise DiscoveryError("Enter a website or feed address.")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    parts = urlsplit(url)
    if not parts.netloc or "." not in parts.netloc:
        raise DiscoveryError("That doesn't look like a web address.")
    if parts.netloc.lower().endswith("reddit.com"):
        raise DiscoveryError("Reddit ended RSS support on 13 November 2026, so subreddits can't be followed.")
    if not parts.path:
        url += "/"
    return url


def _looks_like_feed(resp: httpx.Response) -> bool:
    ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    if ctype in FEED_TYPES and ctype not in ("application/json",):
        return True
    head = resp.text[:600].lstrip().lower()
    return head.startswith("<?xml") or "<rss" in head or "<feed" in head or '"version": "https://jsonfeed.org' in head


def _alternate_links(html: str, base: str) -> list[tuple[str, str]]:
    try:
        doc = lxml.html.fromstring(html)
    except (lxml.etree.ParserError, ValueError):
        return []
    out = []
    for link in doc.xpath("//link[@rel and @href]"):
        rels = (link.get("rel") or "").lower().split()
        ltype = (link.get("type") or "").lower()
        if "alternate" in rels and ltype in FEED_TYPES:
            href = urljoin(base, link.get("href"))
            out.append((href, (link.get("title") or "").strip()))
    seen, unique = set(), []
    for href, title in out:
        # Per-post comment feeds are noise when subscribing to a site.
        if href in seen or "/comments/feed" in href.lower():
            continue
        seen.add(href)
        unique.append((href, title))
    return unique


def _summarize(url: str, parsed: Any, hint_title: str = "") -> dict[str, Any] | None:
    if not parsed.entries and not parsed.feed.get("title"):
        return None
    version = parsed.get("version") or ""
    fmt = "Atom" if version.startswith("atom") else "JSON Feed" if "json" in version else "RSS"
    times = sorted(filter(None, (_entry_time(e) for e in parsed.entries)))
    per_week = None
    if len(times) >= 2:
        from .db import parse_iso

        span_days = max((parse_iso(times[-1]) - parse_iso(times[0])).total_seconds() / 86400, 1)
        per_week = round(len(times) / span_days * 7)
    return {
        "url": url,
        "title": (parsed.feed.get("title") or hint_title or urlsplit(url).netloc).strip(),
        "site_url": parsed.feed.get("link"),
        "format": fmt,
        "per_week": per_week,
        "recent": [(e.get("title") or "").strip() for e in parsed.entries[:2] if e.get("title")],
    }


async def _probe(url: str, hint_title: str = "") -> dict[str, Any] | None:
    try:
        resp = await client().get(url)
    except httpx.HTTPError:
        return None
    if resp.status_code >= 400:
        return None
    parsed = await asyncio.to_thread(feedparser.parse, resp.content)
    if parsed.get("bozo") and not parsed.entries:
        return None
    return _summarize(str(resp.url), parsed, hint_title)


async def discover(raw_url: str) -> list[dict[str, Any]]:
    url = normalize(raw_url)
    try:
        resp = await client().get(url)
    except httpx.HTTPError as exc:
        raise DiscoveryError(f"Couldn't reach that site ({type(exc).__name__}).") from exc
    if resp.status_code >= 400:
        raise DiscoveryError(f"The site answered with HTTP {resp.status_code}.")

    final = str(resp.url)
    if _looks_like_feed(resp):
        parsed = await asyncio.to_thread(feedparser.parse, resp.content)
        found = _summarize(final, parsed)
        if found:
            return [found]

    candidates = _alternate_links(resp.text, final)
    parts = urlsplit(final)
    # Mastodon (and most Fediverse) profiles publish /@user.rss.
    if re.match(r"^/@[\w.]+/?$", parts.path):
        candidates.insert(0, (final.rstrip("/") + ".rss", ""))
    if not candidates:
        root = f"{parts.scheme}://{parts.netloc}"
        candidates = [(root + p, "") for p in COMMON_PATHS]
        if parts.path not in ("", "/"):
            candidates = [(final.rstrip("/") + p, "") for p in COMMON_PATHS[:3]] + candidates

    results = await asyncio.gather(*(_probe(u, t) for u, t in candidates[: MAX_CANDIDATES * 2]))
    found, seen = [], Counter()
    for r in results:
        if r and not seen[r["url"]]:
            seen[r["url"]] += 1
            found.append(r)
    if not found:
        raise DiscoveryError("No feed found on that page. Try pasting the feed address itself.")
    return found[:MAX_CANDIDATES]
