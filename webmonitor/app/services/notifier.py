import logging

import httpx

from app.config import settings
from app.models import MonitoredSite
from app.services.checker import CheckResult

logger = logging.getLogger(__name__)

COLOR_DOWN = 0xE74C3C
COLOR_UP = 0x2ECC71


def _build_payload(site: MonitoredSite, result: CheckResult, event: str) -> dict:
    if event == "down":
        detail = result.error or f"HTTP {result.status_code}"
        return {
            "embeds": [{
                "title": f"🔴 {site.name} no responde",
                "description": f"`{site.url}`\n**Motivo:** {detail}",
                "color": COLOR_DOWN,
            }]
        }

    latency = f"{result.response_time_ms} ms" if result.response_time_ms else "n/d"
    return {
        "embeds": [{
            "title": f"🟢 {site.name} recuperado",
            "description": f"`{site.url}`\n**Latencia:** {latency}",
            "color": COLOR_UP,
        }]
    }


async def send_alert(
    client: httpx.AsyncClient,
    site: MonitoredSite,
    result: CheckResult,
    event: str,
) -> bool:
    """Envía la alerta. Devuelve False si no se pudo enviar, sin lanzar excepción."""
    if not settings.discord_webhook_url:
        logger.warning("Alerta '%s' para %s sin enviar: webhook no configurado",
                       event, site.name)
        return False

    try:
        response = await client.post(
            settings.discord_webhook_url,
            json=_build_payload(site, result, event),
            timeout=10.0,
        )
        response.raise_for_status()
        logger.info("Alerta '%s' enviada para %s", event, site.name)
        return True
    except httpx.HTTPError as exc:
        logger.error("Fallo enviando alerta para %s: %s", site.name, exc)
        return False