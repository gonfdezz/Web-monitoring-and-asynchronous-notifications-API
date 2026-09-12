import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlmodel import select

from app.config import settings
from app.database import async_session
from app.models import HealthLog, MonitoredSite, SiteStatus, utcnow
from app.services.checker import CheckResult, check_many
from app.services.notifier import send_alert

logger = logging.getLogger(__name__)


def is_due(site: MonitoredSite, now: datetime) -> bool:
    """¿Ha pasado ya su intervalo desde la última comprobación?"""
    if site.last_checked_at is None:
        return True
    return now - site.last_checked_at >= timedelta(seconds=site.check_interval)


def apply_result(site: MonitoredSite, result: CheckResult) -> str | None:
    """
    Actualiza el estado del sitio y devuelve el nombre de la transición
    si hay que alertar, o None si no ha cambiado nada relevante.
    """
    site.last_checked_at = utcnow()
    previous = site.status

    if result.is_up:
        site.consecutive_failures = 0
        site.status = SiteStatus.UP
        return "recovered" if previous == SiteStatus.DOWN else None

    site.consecutive_failures += 1
    if site.consecutive_failures >= settings.failure_threshold:
        site.status = SiteStatus.DOWN
        return "down" if previous != SiteStatus.DOWN else None
    return None


async def run_checks(client: httpx.AsyncClient) -> None:
    """Una ronda completa: selecciona, comprueba, persiste y alerta."""
    now = datetime.now(timezone.utc)
    pending: list[tuple[MonitoredSite, CheckResult, str]] = []

    async with async_session() as session:
        stmt = select(MonitoredSite).where(MonitoredSite.is_active == True)  # noqa: E712
        sites = (await session.execute(stmt)).scalars().all()

        due = [s for s in sites if is_due(s, now)]
        if not due:
            return

        logger.info("Comprobando %d sitio(s)", len(due))
        results = await check_many(client, due)
        by_id = {s.id: s for s in due}

        for result in results:
            site = by_id[result.site_id]
            session.add(HealthLog(
                site_id=site.id,
                is_up=result.is_up,
                status_code=result.status_code,
                response_time_ms=result.response_time_ms,
                error=result.error,
            ))
            transition = apply_result(site, result)
            if transition:
                pending.append((site, result, transition))

        await session.commit()

    # Las alertas van FUERA de la transacción, ya con los datos a salvo
    if pending:
        await asyncio.gather(
            *(send_alert(client, s, r, e) for s, r, e in pending)
        )