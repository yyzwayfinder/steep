"""OPML import and export (F-3). Folders are one level deep; deeper nesting flattens to the top folder."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urlsplit
from xml.sax.saxutils import quoteattr

from lxml import etree

from . import db


@dataclass
class OpmlFeed:
    url: str
    title: str | None
    site_url: str | None
    folder: str | None


@dataclass
class ImportReport:
    added: int = 0
    existing: int = 0
    folders_created: int = 0
    skipped_reddit: list[str] = field(default_factory=list)
    invalid: int = 0
    feed_ids: list[int] = field(default_factory=list)


def parse(data: bytes) -> list[OpmlFeed]:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=True, huge_tree=False)
    try:
        root = etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise ValueError("That file isn't valid OPML.") from exc
    if root is None:
        raise ValueError("That file isn't valid OPML.")
    body = root.find("body")
    if body is None:
        raise ValueError("That file has no <body>, so it isn't OPML.")

    feeds: list[OpmlFeed] = []

    def walk(node: etree._Element, folder: str | None) -> None:
        for outline in node.findall("outline"):
            url = outline.get("xmlUrl") or outline.get("xmlurl")
            name = (outline.get("title") or outline.get("text") or "").strip() or None
            if url:
                feeds.append(OpmlFeed(url=url.strip(), title=name, site_url=outline.get("htmlUrl"), folder=folder))
            else:
                walk(outline, folder or name)

    walk(body, None)
    return feeds


def import_feeds(conn: sqlite3.Connection, feeds: Iterable[OpmlFeed], skip_reddit: bool = True) -> ImportReport:
    report = ImportReport()
    now = db.iso()
    with db.transaction(conn):
        folder_ids: dict[str, int] = {
            r["name"].lower(): r["id"] for r in conn.execute("SELECT id, name FROM folders")
        }
        for f in feeds:
            parts = urlsplit(f.url)
            if parts.scheme not in ("http", "https") or not parts.netloc:
                report.invalid += 1
                continue
            if skip_reddit and parts.netloc.lower().endswith("reddit.com"):
                report.skipped_reddit.append(f.title or f.url)
                continue
            folder_id = None
            if f.folder:
                key = f.folder.lower()
                if key not in folder_ids:
                    cur = conn.execute(
                        "INSERT INTO folders(name, sort_order) VALUES (?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM folders))",
                        (f.folder[:100],),
                    )
                    folder_ids[key] = cur.lastrowid
                    report.folders_created += 1
                folder_id = folder_ids[key]
            existing = conn.execute("SELECT id, deleted_at FROM feeds WHERE url=?", (f.url,)).fetchone()
            if existing and not existing["deleted_at"]:
                report.existing += 1
                continue
            if existing:
                conn.execute("UPDATE feeds SET deleted_at=NULL, folder_id=? WHERE id=?", (folder_id, existing["id"]))
                report.feed_ids.append(existing["id"])
            else:
                cur = conn.execute(
                    "INSERT INTO feeds(folder_id, url, site_url, title, created_at) VALUES (?,?,?,?,?)",
                    (folder_id, f.url, f.site_url, f.title, now),
                )
                report.feed_ids.append(cur.lastrowid)
            report.added += 1
    return report


def export(conn: sqlite3.Connection) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<opml version="2.0">',
        f"  <head><title>Steep subscriptions</title><dateCreated>{db.iso()}</dateCreated></head>",
        "  <body>",
    ]

    def outline(feed: sqlite3.Row, indent: str) -> str:
        title = feed["custom_title"] or feed["title"] or feed["url"]
        site = f" htmlUrl={quoteattr(feed['site_url'])}" if feed["site_url"] else ""
        return (f'{indent}<outline type="rss" text={quoteattr(title)} title={quoteattr(title)} '
                f"xmlUrl={quoteattr(feed['url'])}{site}/>")

    for folder in conn.execute("SELECT * FROM folders ORDER BY sort_order, name"):
        lines.append(f"    <outline text={quoteattr(folder['name'])} title={quoteattr(folder['name'])}>")
        for feed in conn.execute(
            "SELECT * FROM feeds WHERE folder_id=? AND deleted_at IS NULL ORDER BY sort_order, COALESCE(custom_title, title)",
            (folder["id"],),
        ):
            lines.append(outline(feed, "      "))
        lines.append("    </outline>")
    for feed in conn.execute(
        "SELECT * FROM feeds WHERE folder_id IS NULL AND deleted_at IS NULL ORDER BY COALESCE(custom_title, title)"
    ):
        lines.append(outline(feed, "    "))
    lines += ["  </body>", "</opml>", ""]
    return "\n".join(lines)
