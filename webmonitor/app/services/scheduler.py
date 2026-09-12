import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.monitor import run_checks

logger = logging.getLogger(__name__)

TICK_SECONDS = 15

scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler(client: httpx.AsyncClient) -> None:
    scheduler.add_job(
        run_checks,
        trigger="interval",
        seconds=TICK_SECONDS,
        args=[client],
        id="monitor_tick",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
    )
    scheduler.start()
    logger.info("Scheduler arrancado (tick cada %ds)", TICK_SECONDS)


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido")