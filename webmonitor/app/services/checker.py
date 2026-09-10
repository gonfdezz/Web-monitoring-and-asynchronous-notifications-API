import asyncio
import time
from dataclasses import dataclass

import httpx

from app.config import settings
from app.models import MonitoredSite


@dataclass
class CheckResult:
    site_id: int
    is_up: bool
    status_code: int | None = None
    response_time_ms: float | None = None
    error: str | None = None


async def check_site(client: httpx.AsyncClient, site: MonitoredSite) -> CheckResult:
    """Comprueba un sitio. Nunca lanza excepción: los fallos son datos."""
    start = time.perf_counter()
    try:
        response = await client.get(
            site.url,
            timeout=settings.request_timeout,
            follow_redirects=True,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        return CheckResult(
            site_id=site.id,
            is_up=200 <= response.status_code < 400,
            status_code=response.status_code,
            response_time_ms=round(elapsed_ms, 2),
        )

    except httpx.TimeoutException:
        return CheckResult(
            site_id=site.id,
            is_up=False,
            error=f"Timeout tras {settings.request_timeout}s",
        )

    except httpx.RequestError as exc:
        return CheckResult(
            site_id=site.id,
            is_up=False,
            error=f"{type(exc).__name__}: {exc}",
        )


async def check_many(
    client: httpx.AsyncClient, sites: list[MonitoredSite]
) -> list[CheckResult]:
    """Comprueba todos los sitios concurrentemente."""
    results = await asyncio.gather(
        *(check_site(client, site) for site in sites),
        return_exceptions=True,
    )

    final: list[CheckResult] = []
    for site, result in zip(sites, results):
        if isinstance(result, BaseException):
            final.append(
                CheckResult(
                    site_id=site.id,
                    is_up=False,
                    error=f"Error interno: {type(result).__name__}: {result}",
                )
            )
        else:
            final.append(result)
    return final