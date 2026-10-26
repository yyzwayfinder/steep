"""JSON API under /api."""

from __future__ import annotations

import asyncio
import re
import sqlite3
from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import __version__, auth, db, discovery, fetcher, opml
from .events import broadcaster

public = APIRouter(prefix="/api")
router = APIRouter(prefix="/api", dependencies=[Depends(auth.require_user)])

Scope = Literal["all", "saved", "folder", "feed"]
PAGE = 40


def conn_dep():
    with db.connect() as conn:
        yield conn


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(r) if r is not None else None


def _feed_title(r: sqlite3.Row) -> str:
    return r["custom_title"] or r["title"] or r["url"]


# ------------------------------------------------------------------ auth


class LoginBody(BaseModel):
    password: str = Field(max_length=500)


@public.get("/me")
def me(request: Request):
    return {"authenticated": auth.is_authenticated(request), "version": __version__}


@public.post("/login")
async def login(body: LoginBody, request: Request, response: Response):
    if not auth.check_password(body.password):
        await auth.slow_down()
        raise HTTPException(401, "That password didn't match.")
    auth.issue(response, request)
    return {"ok": True}


@public.post("/logout")
def logout(response: Response):
    auth.clear(response)
    return {"ok": True}


# ------------------------------------------------------------------ sidebar tree


@router.get("/tree")
def tree(conn: sqlite3.Connection = Depends(conn_dep)):
    unread = {r["feed_id"]: r["n"] for r in conn.execute(
        "SELECT feed_id, COUNT(*) n FROM articles WHERE read_at IS NULL GROUP BY feed_id")}
    feeds = conn.execute(
        "SELECT * FROM feeds WHERE deleted_at IS NULL ORDER BY sort_order, LOWER(COALESCE(custom_title, title, url))"
    ).fetchall()
    folders = [dict(r) | {"feeds": [], "unread": 0} for r in conn.execute("SELECT * FROM folders ORDER BY sort_order, name")]
    by_id = {f["id"]: f for f in folders}
    loose: list[dict] = []
    total = 0
    for f in feeds:
        n = unread.get(f["id"], 0)
        item = {
            "id": f["id"], "title": _feed_title(f), "url": f["url"], "site_url": f["site_url"],
            "favicon_url": f["favicon_url"], "unread": n, "muted": bool(f["muted"]),
            "fulltext": bool(f["fulltext"]), "refresh_minutes": f["refresh_minutes"],
            "folder_id": f["folder_id"], "error": f["last_error"] if f["fail_count"] >= 3 else None,
        }
        if not f["muted"]:
            total += n
        target = by_id.get(f["folder_id"])
        if target:
            target["feeds"].append(item)
            target["unread"] += 0 if f["muted"] else n
        else:
            loose.append(item)
    saved = conn.execute("SELECT COUNT(*) FROM articles WHERE saved_at IS NOT NULL").fetchone()[0]
    last_sync = conn.execute("SELECT MAX(last_success_at) FROM feeds WHERE deleted_at IS NULL").fetchone()[0]
    return {"folders": folders, "uncategorized": loose, "unread": total, "saved": saved, "last_sync": last_sync}


# ------------------------------------------------------------------ folders


class FolderBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class FolderPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None


@router.post("/folders")
def create_folder(body: FolderBody, conn: sqlite3.Connection = Depends(conn_dep)):
    try:
        cur = conn.execute(
            "INSERT INTO folders(name, sort_order) VALUES (?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM folders))",
            (body.name.strip(),),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "A folder with that name already exists.")
    return {"id": cur.lastrowid, "name": body.name.strip()}


@router.patch("/folders/{folder_id}")
def update_folder(folder_id: int, body: FolderPatch, conn: sqlite3.Connection = Depends(conn_dep)):
    if body.name is not None:
        try:
            conn.execute("UPDATE folders SET name=? WHERE id=?", (body.name.strip(), folder_id))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "A folder with that name already exists.")
    if body.sort_order is not None:
        conn.execute("UPDATE folders SET sort_order=? WHERE id=?", (body.sort_order, folder_id))
    return {"ok": True}


@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: int, conn: sqlite3.Connection = Depends(conn_dep)):
    conn.execute("DELETE FROM folders WHERE id=?", (folder_id,))  # feeds fall back to Uncategorized
    return {"ok": True}


# ------------------------------------------------------------------ feeds


class DiscoverBody(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


class FeedCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    folder_id: int | None = None
    title: str | None = Field(default=None, max_length=300)
    fulltext: bool = True


class FeedPatch(BaseModel):
    folder_id: int | None = None
    move_to_uncategorized: bool = False
    custom_title: str | None = Field(default=None, max_length=300)
    refresh_minutes: int | None = Field(default=None, ge=5, le=1440)
    fulltext: bool | None = None
    muted: bool | None = None


@router.post("/discover")
async def discover_feeds(body: DiscoverBody):
    try:
        return {"feeds": await discovery.discover(body.url)}
    except discovery.DiscoveryError as exc:
        raise HTTPException(422, str(exc))


@router.post("/feeds")
def add_feed(body: FeedCreate, tasks: BackgroundTasks, conn: sqlite3.Connection = Depends(conn_dep)):
    url = body.url.strip()
    if not re.match(r"^https?://", url):
        raise HTTPException(422, "Feed URL must start with http:// or https://")
    existing = conn.execute("SELECT id, deleted_at FROM feeds WHERE url=?", (url,)).fetchone()
    if existing and not existing["deleted_at"]:
        raise HTTPException(409, "You're already subscribed to that feed.")
    if existing:
        conn.execute("UPDATE feeds SET deleted_at=NULL, folder_id=?, fulltext=? WHERE id=?",
                     (body.folder_id, int(body.fulltext), existing["id"]))
        feed_id = existing["id"]
    else:
        cur = conn.execute(
            "INSERT INTO feeds(folder_id, url, title, fulltext, created_at) VALUES (?,?,?,?,?)",
            (body.folder_id, url, body.title, int(body.fulltext), db.iso()),
        )
        feed_id = cur.lastrowid
    tasks.add_task(fetcher.fetch_feed, feed_id)
    broadcaster.publish("tree")
    return {"id": feed_id}


@router.patch("/feeds/{feed_id}")
def update_feed(feed_id: int, body: FeedPatch, conn: sqlite3.Connection = Depends(conn_dep)):
    sets: list[str] = []
    args: list[Any] = []
    if body.move_to_uncategorized:
        sets.append("folder_id=NULL")
    elif body.folder_id is not None:
        sets.append("folder_id=?"); args.append(body.folder_id)
    if body.custom_title is not None:
        sets.append("custom_title=?"); args.append(body.custom_title.strip() or None)
    if "refresh_minutes" in body.model_fields_set:
        sets.append("refresh_minutes=?"); args.append(body.refresh_minutes)
    if body.fulltext is not None:
        sets.append("fulltext=?"); args.append(int(body.fulltext))
    if body.muted is not None:
        sets.append("muted=?"); args.append(int(body.muted))
    if sets:
        conn.execute(f"UPDATE feeds SET {', '.join(sets)} WHERE id=?", (*args, feed_id))
    broadcaster.publish("tree")
    return {"ok": True}


@router.delete("/feeds/{feed_id}")
def unsubscribe(feed_id: int, conn: sqlite3.Connection = Depends(conn_dep)):
    """Soft delete so the toast's Undo can bring it back; purged after 10 minutes."""
    conn.execute("UPDATE feeds SET deleted_at=? WHERE id=?", (db.iso(), feed_id))
    broadcaster.publish("tree")
    return {"ok": True}


@router.post("/feeds/{feed_id}/restore")
def restore_feed(feed_id: int, conn: sqlite3.Connection = Depends(conn_dep)):
    conn.execute("UPDATE feeds SET deleted_at=NULL WHERE id=?", (feed_id,))
    broadcaster.publish("tree")
    return {"ok": True}


@router.get("/feeds/health")
def feed_health(conn: sqlite3.Connection = Depends(conn_dep)):
    rows = conn.execute(
        "SELECT f.*, (SELECT MAX(published_at) FROM articles a WHERE a.feed_id=f.id) AS newest "
        "FROM feeds f WHERE deleted_at IS NULL ORDER BY fail_count DESC, LOWER(COALESCE(custom_title,title,url))"
    ).fetchall()
    return {"feeds": [{
        "id": r["id"], "title": _feed_title(r), "url": r["url"], "last_fetch_at": r["last_fetch_at"],
        "last_success_at": r["last_success_at"], "last_status": r["last_status"], "last_error": r["last_error"],
        "fail_count": r["fail_count"], "next_fetch_at": r["next_fetch_at"], "newest_article": r["newest"],
    } for r in rows]}


# ------------------------------------------------------------------ articles

LIST_COLUMNS = (
    "a.id, a.feed_id, a.url, a.title, a.author, a.published_at, a.excerpt, a.image_url, a.updated_at, "
    "a.read_at IS NOT NULL AS is_read, a.saved_at IS NOT NULL AS is_saved, "
    "COALESCE(f.custom_title, f.title, f.url) AS feed_title, f.favicon_url, f.folder_id"
)


def _fts_query(q: str) -> str | None:
    words = re.findall(r"[\w'’-]+", q, flags=re.UNICODE)
    if not words:
        return None
    parts = ['"' + w.replace('"', "") + '"' for w in words]
    parts[-1] += "*"
    return " ".join(parts)


def _scope_sql(scope: Scope, scope_id: int | None, unread: bool, q: str | None) -> tuple[str, list[Any]]:
    where = ["f.deleted_at IS NULL"]
    args: list[Any] = []
    if scope == "all":
        where.append("f.muted = 0")
    elif scope == "saved":
        where.append("a.saved_at IS NOT NULL")
    elif scope == "folder":
        if scope_id:
            where.append("f.folder_id = ?"); args.append(scope_id)
        else:
            where.append("f.folder_id IS NULL")
    elif scope == "feed":
        where.append("a.feed_id = ?"); args.append(scope_id)
    if unread and scope != "saved":
        where.append("a.read_at IS NULL")
    if q:
        match = _fts_query(q)
        if match:
            where.append("a.id IN (SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?)")
            args.append(match)
    return " AND ".join(where), args


@router.get("/articles")
def list_articles(
    scope: Scope = "all",
    id: int | None = None,
    unread: bool = True,
    q: str | None = Query(default=None, max_length=200),
    cursor: str | None = None,
    limit: int = Query(default=PAGE, ge=1, le=100),
    conn: sqlite3.Connection = Depends(conn_dep),
):
    where, args = _scope_sql(scope, id, unread, q)
    order_col = "a.saved_at" if scope == "saved" else "a.published_at"
    if cursor:
        try:
            ts, cid = cursor.rsplit("|", 1)
            where += f" AND ({order_col} < ? OR ({order_col} = ? AND a.id < ?))"
            args += [ts, ts, int(cid)]
        except ValueError:
            raise HTTPException(400, "Bad cursor")
    rows = conn.execute(
        f"SELECT {LIST_COLUMNS}, {order_col} AS sort_key FROM articles a JOIN feeds f ON f.id = a.feed_id "
        f"WHERE {where} ORDER BY {order_col} DESC, a.id DESC LIMIT ?",
        (*args, limit + 1),
    ).fetchall()
    items = [dict(r) for r in rows[:limit]]
    next_cursor = None
    if len(rows) > limit:
        last = items[-1]
        next_cursor = f"{last['sort_key']}|{last['id']}"
    for it in items:
        it["is_read"] = bool(it["is_read"]); it["is_saved"] = bool(it["is_saved"])
        it.pop("sort_key", None)
    total = conn.execute(
        f"SELECT COUNT(*) FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE {_scope_sql(scope, id, unread, q)[0]}",
        _scope_sql(scope, id, unread, q)[1],
    ).fetchone()[0] if not cursor else None
    return {"items": items, "next_cursor": next_cursor, "total": total}


@router.get("/articles/{article_id}")
def get_article(article_id: int, conn: sqlite3.Connection = Depends(conn_dep)):
    r = conn.execute(
        f"SELECT {LIST_COLUMNS}, a.content_html, a.summary_html, a.extracted, a.extract_failed, a.read_progress, "
        "f.site_url FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE a.id=?",
        (article_id,),
    ).fetchone()
    if r is None:
        raise HTTPException(404, "Article not found")
    out = dict(r)
    out["is_read"] = bool(out["is_read"]); out["is_saved"] = bool(out["is_saved"])
    words = len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", out["content_html"] or "")))
    out["minutes"] = max(1, round(words / 230)) if words else None
    return out


class FlagBody(BaseModel):
    value: bool


class ProgressBody(BaseModel):
    progress: float = Field(ge=0, le=1)


@router.post("/articles/{article_id}/read")
def set_read(article_id: int, body: FlagBody, conn: sqlite3.Connection = Depends(conn_dep)):
    conn.execute("UPDATE articles SET read_at=? WHERE id=?", (db.iso() if body.value else None, article_id))
    broadcaster.publish("counts")
    return {"ok": True}


@router.post("/articles/{article_id}/save")
def set_saved(article_id: int, body: FlagBody, conn: sqlite3.Connection = Depends(conn_dep)):
    conn.execute("UPDATE articles SET saved_at=? WHERE id=?", (db.iso() if body.value else None, article_id))
    broadcaster.publish("counts")
    return {"ok": True}


@router.post("/articles/{article_id}/progress")
def set_progress(article_id: int, body: ProgressBody, conn: sqlite3.Connection = Depends(conn_dep)):
    conn.execute("UPDATE articles SET read_progress=? WHERE id=?", (body.progress, article_id))
    if 0.05 < body.progress < 0.92:
        db.set_setting(conn, "continue_article", str(article_id))
    elif db.get_setting(conn, "continue_article") == str(article_id):
        db.set_setting(conn, "continue_article", "")
    return {"ok": True}


class MarkReadBody(BaseModel):
    scope: Scope = "all"
    id: int | None = None
    older_than: Literal["none", "1d", "1w"] = "none"
    q: str | None = None


class IdsBody(BaseModel):
    ids: list[int] = Field(max_length=50_000)


@router.post("/mark-read")
def mark_read(body: MarkReadBody, conn: sqlite3.Connection = Depends(conn_dep)):
    where, args = _scope_sql(body.scope, body.id, True, body.q)
    if body.older_than != "none":
        delta = timedelta(days=1 if body.older_than == "1d" else 7)
        where += " AND a.published_at < ?"
        args.append(db.iso(db.utcnow() - delta))
    with db.transaction(conn):
        ids = [r[0] for r in conn.execute(
            f"SELECT a.id FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE {where}", args)]
        now = db.iso()
        for chunk in range(0, len(ids), 500):
            part = ids[chunk:chunk + 500]
            conn.execute(f"UPDATE articles SET read_at=? WHERE id IN ({','.join('?' * len(part))})", (now, *part))
    broadcaster.publish("counts")
    return {"count": len(ids), "ids": ids}


@router.post("/mark-unread")
def mark_unread(body: IdsBody, conn: sqlite3.Connection = Depends(conn_dep)):
    with db.transaction(conn):
        for chunk in range(0, len(body.ids), 500):
            part = body.ids[chunk:chunk + 500]
            conn.execute(f"UPDATE articles SET read_at=NULL WHERE id IN ({','.join('?' * len(part))})", part)
    broadcaster.publish("counts")
    return {"count": len(body.ids)}


# ------------------------------------------------------------------ home (launch screen)


@router.get("/home")
def home(open: bool = False, conn: sqlite3.Connection = Depends(conn_dep)):
    """Status for the iPhone launch screen. `open=1` marks a new app session."""
    now = db.utcnow()
    last_open = db.parse_iso(db.get_setting(conn, "last_open") or None)
    prev_open = db.get_setting(conn, "prev_open") or None
    resume_minutes = int(db.get_setting(conn, "resume_minutes") or 60)
    resume = bool(last_open and now - last_open < timedelta(minutes=resume_minutes))
    if open:
        if last_open and now - last_open > timedelta(minutes=30):
            prev_open = db.iso(last_open)
            db.set_setting(conn, "prev_open", prev_open)
        db.set_setting(conn, "last_open", db.iso(now))
    since = prev_open or db.iso(now - timedelta(days=1))
    new = conn.execute(
        "SELECT COUNT(*) FROM articles a JOIN feeds f ON f.id=a.feed_id "
        "WHERE a.read_at IS NULL AND f.deleted_at IS NULL AND f.muted=0 AND a.fetched_at > ?",
        (since,),
    ).fetchone()[0]
    cont = None
    cid = db.get_setting(conn, "continue_article")
    if cid:
        r = conn.execute(
            "SELECT a.id, a.title, a.image_url, a.read_progress, COALESCE(f.custom_title, f.title) AS feed_title "
            "FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE a.id=?", (int(cid),)
        ).fetchone()
        cont = _row(r)
    last_sync = conn.execute("SELECT MAX(last_success_at) FROM feeds WHERE deleted_at IS NULL").fetchone()[0]
    return {"since": since, "new": new, "last_sync": last_sync, "continue": cont, "resume": resume}


@router.post("/home/dismiss-continue")
def dismiss_continue(conn: sqlite3.Connection = Depends(conn_dep)):
    db.set_setting(conn, "continue_article", "")
    return {"ok": True}


# ------------------------------------------------------------------ OPML, refresh, settings


@router.post("/opml/import")
async def import_opml(tasks: BackgroundTasks, file: UploadFile = File(...)):
    data = await file.read(10_000_001)
    if len(data) > 10_000_000:
        raise HTTPException(413, "That file is larger than 10 MB.")
    try:
        feeds = opml.parse(data)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    with db.connect() as conn:
        skip = db.get_setting(conn, "skip_reddit_on_import") == "1"
        report = opml.import_feeds(conn, feeds, skip_reddit=skip)
    if report.feed_ids:
        tasks.add_task(fetcher.refresh, report.feed_ids)
    broadcaster.publish("tree")
    return {"added": report.added, "existing": report.existing, "folders_created": report.folders_created,
            "skipped_reddit": report.skipped_reddit, "invalid": report.invalid}


@router.get("/opml/export")
def export_opml(conn: sqlite3.Connection = Depends(conn_dep)):
    return PlainTextResponse(
        opml.export(conn), media_type="text/x-opml",
        headers={"Content-Disposition": 'attachment; filename="steep-subscriptions.opml"'},
    )


class RefreshBody(BaseModel):
    scope: Scope = "all"
    id: int | None = None


@router.post("/refresh")
async def refresh_now(body: RefreshBody):
    with db.connect() as conn:
        if body.scope == "feed" and body.id:
            ids = [body.id]
        elif body.scope == "folder":
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM feeds WHERE deleted_at IS NULL AND " + ("folder_id=?" if body.id else "folder_id IS NULL"),
                (body.id,) if body.id else ())]
        else:
            ids = [r[0] for r in conn.execute("SELECT id FROM feeds WHERE deleted_at IS NULL")]
    asyncio.create_task(fetcher.refresh(ids))
    return {"queued": len(ids)}


SETTING_KEYS = {"retention_days", "updated_marks_unread", "resume_minutes", "skip_reddit_on_import"}


@router.get("/settings")
def get_settings_api(conn: sqlite3.Connection = Depends(conn_dep)):
    return {k: v for k, v in db.all_settings(conn).items() if k in SETTING_KEYS}


@router.patch("/settings")
def patch_settings(body: dict[str, str], conn: sqlite3.Connection = Depends(conn_dep)):
    for k, v in body.items():
        if k not in SETTING_KEYS:
            raise HTTPException(422, f"Unknown setting {k}")
        if k in {"retention_days", "resume_minutes"} and not str(v).isdigit():
            raise HTTPException(422, f"{k} must be a whole number")
        db.set_setting(conn, k, str(v))
    return {"ok": True}


# ------------------------------------------------------------------ live updates


@router.get("/events")
async def events(request: Request):
    queue = broadcaster.subscribe()

    async def stream():
        try:
            yield "retry: 5000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=25)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
