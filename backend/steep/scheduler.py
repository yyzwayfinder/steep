"""Background jobs: poll due feeds every minute, purge old articles nightly."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import db, fetcher

log = logging.getLogger("steep.scheduler")
_scheduler: AsyncIOScheduler | None = None
_running = asyncio.Lock()


async def poll() -> None:
    if _running.locked():
        return  # a slow sweep is still going; skip this tick
    async with _running:
        totals = await fetcher.refresh_due()
        if totals["feeds"]:
            log.info("sync: %s", totals)


def purge_job() -> None:
    with db.connect() as conn:
        n = fetcher.purge(conn)
        if n:
            log.info("purged %d old articles", n)
        conn.execute("PRAGMA optimize")


def start() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(poll, "interval", seconds=60, id="poll", max_instances=1, coalesce=True)
    _scheduler.add_job(purge_job, "interval", minutes=10, id="purge", max_instances=1, coalesce=True)
    _scheduler.start()
    # First sweep shortly after startup.
    asyncio.get_running_loop().call_later(3, lambda: asyncio.ensure_future(poll()))


def stop() -> None:
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
