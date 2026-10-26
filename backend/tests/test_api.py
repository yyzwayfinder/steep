import asyncio

import pytest
from conftest import fixture
from fastapi.testclient import TestClient

from steep import db, fetcher


@pytest.fixture
def client(web):
    from steep.main import create_app

    with TestClient(create_app()) as c:
        yield c


def login(c):
    assert c.post("/api/login", json={"password": "test-password"}).status_code == 200
    c.headers["X-Steep"] = "1"


def seed(web):
    web.add("https://lakeshore.example/feeds/local.atom", fixture("local.atom"), content_type="application/atom+xml")
    with db.connect() as conn:
        folder = conn.execute("INSERT INTO folders(name) VALUES ('News')").lastrowid
        fid = conn.execute("INSERT INTO feeds(url, folder_id, fulltext, created_at) VALUES (?,?,0,?)",
                           ("https://lakeshore.example/feeds/local.atom", folder, db.iso())).lastrowid
    asyncio.run(fetcher.fetch_feed(fid))
    return folder, fid


def test_requires_login_and_csrf_header(client):
    assert client.get("/api/tree").status_code == 401
    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    client.post("/api/login", json={"password": "test-password"})
    assert client.get("/api/tree").status_code == 200
    assert client.post("/api/mark-read", json={}).status_code == 403  # no X-Steep header
    client.headers["X-Steep"] = "1"
    assert client.post("/api/mark-read", json={}).status_code == 200


def test_tree_list_read_and_undo(client, web):
    folder, fid = seed(web)
    login(client)
    tree = client.get("/api/tree").json()
    assert tree["unread"] == 2
    assert tree["folders"][0]["feeds"][0]["unread"] == 2

    page = client.get("/api/articles", params={"scope": "folder", "id": folder}).json()
    assert [i["title"] for i in page["items"]][0].startswith("Council backs")
    assert page["total"] == 2

    article = client.get(f"/api/articles/{page['items'][0]['id']}").json()
    assert "construction" in article["content_html"]

    done = client.post("/api/mark-read", json={"scope": "all"}).json()
    assert done["count"] == 2
    assert client.get("/api/tree").json()["unread"] == 0
    client.post("/api/mark-unread", json={"ids": done["ids"]})
    assert client.get("/api/tree").json()["unread"] == 2


def test_mark_read_older_than_respects_age(client, web):
    seed(web)
    login(client)
    with db.connect() as conn:
        conn.execute("UPDATE articles SET published_at=? WHERE guid='urn:lakeshore:local:2'", ("2020-01-01T00:00:00Z",))
        conn.execute("UPDATE articles SET published_at=? WHERE guid='urn:lakeshore:local:1'", (db.iso(),))
    assert client.post("/api/mark-read", json={"scope": "all", "older_than": "1d"}).json()["count"] == 1


def test_search_save_and_saved_scope(client, web):
    seed(web)
    login(client)
    hits = client.get("/api/articles", params={"q": "constru", "unread": "false"}).json()["items"]
    assert len(hits) == 1
    client.post(f"/api/articles/{hits[0]['id']}/save", json={"value": True})
    saved = client.get("/api/articles", params={"scope": "saved"}).json()["items"]
    assert [s["id"] for s in saved] == [hits[0]["id"]]


def test_unsubscribe_hides_feed_until_restored(client, web):
    _, fid = seed(web)
    login(client)
    client.delete(f"/api/feeds/{fid}")
    assert client.get("/api/tree").json()["unread"] == 0
    client.post(f"/api/feeds/{fid}/restore")
    assert client.get("/api/tree").json()["unread"] == 2


def test_opml_import_and_export(client):
    login(client)
    from conftest import FIXTURES

    with open(FIXTURES / "feedly.opml", "rb") as fh:
        report = client.post("/api/opml/import", files={"file": ("feedly.opml", fh, "text/xml")}).json()
    assert report["added"] == 4 and report["skipped_reddit"] == ["r/selfhosted"]
    out = client.get("/api/opml/export")
    assert "signal.example/feed" in out.text and "reddit" not in out.text


def test_home_tracks_sessions(client, web):
    seed(web)
    login(client)
    first = client.get("/api/home", params={"open": "true"}).json()
    assert first["new"] == 2 and first["resume"] is False
    again = client.get("/api/home").json()
    assert again["resume"] is True


def test_healthz_and_security_headers(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert "default-src 'self'" in r.headers["content-security-policy"]
