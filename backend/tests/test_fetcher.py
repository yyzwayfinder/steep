import asyncio

from conftest import fixture

from steep import db, discovery, fetcher


def add_feed(url: str, fulltext: bool = True) -> int:
    with db.connect() as conn:
        return conn.execute(
            "INSERT INTO feeds(url, fulltext, created_at) VALUES (?, ?, ?)", (url, int(fulltext), db.iso())
        ).lastrowid


def articles():
    with db.connect() as conn:
        return {r["guid"]: dict(r) for r in conn.execute("SELECT * FROM articles")}


def test_fetch_stores_items_extracts_teasers_and_cleans_links(web):
    web.add("https://signal.example/feed", fixture("teaser.rss"), headers={"etag": '"v1"'})
    web.add("https://signal.example/home-server?id=7", fixture("article.html"), content_type="text/html")
    web.add("https://signal.example/rss-never-died", "<html><body>tiny</body></html>", content_type="text/html")
    fid = add_feed("https://signal.example/feed")

    report = asyncio.run(fetcher.fetch_feed(fid))
    assert report == {"new": 2, "updated": 0, "error": None}

    items = articles()
    teaser = items["https://signal.example/?p=101"]
    assert teaser["url"] == "https://signal.example/home-server?id=7"  # utm params stripped
    assert teaser["extracted"] == 1
    assert "closet" in teaser["content_html"]
    assert "https://signal.example/img/rack.jpg" in teaser["content_html"]  # relative image made absolute
    assert teaser["excerpt"].startswith("Cheap storage, better containers")  # from the body, not the teaser
    assert teaser["image_url"] == "https://signal.example/img/server.jpg"

    long_summary = items["https://signal.example/?p=100"]
    assert "<script" not in long_summary["content_html"]
    assert "pixel.gif" not in long_summary["content_html"]
    assert long_summary["excerpt"].startswith("Feed readers are having a moment")

    with db.connect() as conn:
        feed = conn.execute("SELECT * FROM feeds WHERE id=?", (fid,)).fetchone()
        assert feed["title"] == "Signal & Noise"
        assert feed["etag"] == '"v1"'
        assert feed["fail_count"] == 0

    # Second run: server answers 304, nothing duplicated.
    assert asyncio.run(fetcher.fetch_feed(fid))["new"] == 0
    assert web.requests[-1].headers["if-none-match"] == '"v1"'
    assert len(articles()) == 2


def test_changed_content_is_flagged_updated_not_duplicated(web):
    atom = fixture("local.atom")
    web.add("https://lakeshore.example/feeds/local.atom", atom, content_type="application/atom+xml")
    fid = add_feed("https://lakeshore.example/feeds/local.atom", fulltext=False)
    asyncio.run(fetcher.fetch_feed(fid))
    with db.connect() as conn:
        conn.execute("UPDATE articles SET read_at=?", (db.iso(),))

    web.add("https://lakeshore.example/feeds/local.atom", atom.replace("pencilled in for 2028", "now set for 2029"),
            content_type="application/atom+xml")
    report = asyncio.run(fetcher.fetch_feed(fid))
    assert report["updated"] == 1 and report["new"] == 0
    changed = articles()["urn:lakeshore:local:1"]
    assert changed["updated_at"] is not None
    assert changed["read_at"] is not None  # default: tag only, stays read


def test_failures_back_off(web):
    fid = add_feed("https://gone.example/feed")
    asyncio.run(fetcher.fetch_feed(fid))
    asyncio.run(fetcher.fetch_feed(fid))
    with db.connect() as conn:
        feed = conn.execute("SELECT * FROM feeds WHERE id=?", (fid,)).fetchone()
    assert feed["fail_count"] == 2
    assert feed["last_error"] == "HTTP 404"
    gap = db.parse_iso(feed["next_fetch_at"]) - db.parse_iso(feed["last_fetch_at"])
    assert gap.total_seconds() >= 30 * 60 * 4


def test_purge_keeps_saved_and_tombstones_the_rest(web):
    web.add("https://lakeshore.example/feeds/local.atom", fixture("local.atom"), content_type="application/atom+xml")
    fid = add_feed("https://lakeshore.example/feeds/local.atom", fulltext=False)
    asyncio.run(fetcher.fetch_feed(fid))
    with db.connect() as conn:
        conn.execute("UPDATE articles SET read_at=?, published_at='2020-01-01T00:00:00Z'", (db.iso(),))
        conn.execute("UPDATE articles SET saved_at=? WHERE guid='urn:lakeshore:local:2'", (db.iso(),))
        assert fetcher.purge(conn) == 1
    assert list(articles()) == ["urn:lakeshore:local:2"]
    # The purged item must not come back as new on the next fetch.
    assert asyncio.run(fetcher.fetch_feed(fid))["new"] == 0


def test_discovery_finds_alternate_links_and_skips_comment_feeds(web):
    web.add("https://lakeshore.example/", fixture("site.html"), content_type="text/html")
    web.add("https://lakeshore.example/feeds/top.xml", fixture("teaser.rss"))
    web.add("https://lakeshore.example/feeds/local.atom", fixture("local.atom"), content_type="application/atom+xml")
    found = asyncio.run(discovery.discover("lakeshore.example"))
    assert [f["format"] for f in found] == ["RSS", "Atom"]
    assert found[1]["recent"][0].startswith("Council backs")
    assert all("comments" not in f["url"] for f in found)


def test_discovery_refuses_reddit():
    import pytest

    with pytest.raises(discovery.DiscoveryError, match="Reddit"):
        asyncio.run(discovery.discover("https://www.reddit.com/r/selfhosted"))
