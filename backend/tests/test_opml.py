from conftest import FIXTURES

from steep import db, opml


def test_import_feedly_export_maps_folders_and_skips_reddit():
    feeds = opml.parse((FIXTURES / "feedly.opml").read_bytes())
    with db.connect() as conn:
        report = opml.import_feeds(conn, feeds, skip_reddit=True)
        assert report.added == 4
        assert report.skipped_reddit == ["r/selfhosted"]
        assert report.invalid == 1
        assert report.folders_created == 2
        rows = {r["url"]: r for r in conn.execute(
            "SELECT feeds.url, folders.name AS folder FROM feeds LEFT JOIN folders ON folders.id = feeds.folder_id")}
        assert rows["https://signal.example/feed"]["folder"] == "Tech"
        assert rows["https://deep.example/rss"]["folder"] == "Tech"  # nested group flattened
        assert rows["https://loose.example/feed.xml"]["folder"] is None

        again = opml.import_feeds(conn, feeds, skip_reddit=True)
        assert again.added == 0 and again.existing == 4


def test_export_round_trips():
    feeds = opml.parse((FIXTURES / "feedly.opml").read_bytes())
    with db.connect() as conn:
        opml.import_feeds(conn, feeds)
        text = opml.export(conn)
    reparsed = opml.parse(text.encode())
    assert {f.url for f in reparsed} == {f.url for f in feeds if "reddit" not in f.url and f.url.startswith("http")}


def test_rejects_non_opml():
    import pytest

    with pytest.raises(ValueError):
        opml.parse(b"<html><p>nope</p></html>")
