import os
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("STEEP_PASSWORD", "test-password")
os.environ.setdefault("STEEP_DISABLE_SCHEDULER", "1")

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    from steep import config, db

    monkeypatch.setenv("STEEP_DATA_DIR", str(tmp_path))
    config.settings = None
    db.migrate()
    yield tmp_path
    config.settings = None


class FakeWeb:
    """Serves fixture files for given URLs; records requests."""

    def __init__(self):
        self.routes: dict[str, tuple[int, bytes, dict]] = {}
        self.requests: list[httpx.Request] = []

    def add(self, url, body, status=200, content_type="application/rss+xml", headers=None):
        if isinstance(body, str):
            body = body.encode()
        self.routes[url] = (status, body, {"content-type": content_type, **(headers or {})})

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if url not in self.routes:
            return httpx.Response(404, text="not found")
        status, body, headers = self.routes[url]
        etag = headers.get("etag")
        if etag and request.headers.get("if-none-match") == etag:
            return httpx.Response(304)
        return httpx.Response(status, content=body, headers=headers)


@pytest.fixture
def web(monkeypatch):
    from steep import fetcher

    fake = FakeWeb()
    client = httpx.AsyncClient(transport=httpx.MockTransport(fake.handler), follow_redirects=True)
    monkeypatch.setattr(fetcher, "_client", client)
    return fake


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()
