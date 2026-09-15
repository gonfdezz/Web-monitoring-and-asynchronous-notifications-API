import httpx
import pytest

from app.models import MonitoredSite
from app.services.checker import check_many, check_site


def make_site(site_id=1, url="https://test.com") -> MonitoredSite:
    return MonitoredSite(id=site_id, name=f"Site {site_id}", url=url)


async def run_with(handler, site):
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        return await check_site(client, site)


@pytest.mark.parametrize("code, esperado", [(200, True), (301, True), (404, False), (500, False)])
async def test_rango_de_codigos(code, esperado):
    result = await run_with(lambda req: httpx.Response(code), make_site())
    assert result.is_up is esperado
    assert result.status_code == code
    assert result.response_time_ms is not None


async def test_timeout_no_lanza_excepcion():
    def handler(request):
        raise httpx.TimeoutException("agotado", request=request)

    result = await run_with(handler, make_site())

    assert result.is_up is False
    assert result.status_code is None
    assert result.response_time_ms is None      # ← clave para las métricas
    assert "Timeout" in result.error


async def test_error_de_conexion():
    def handler(request):
        raise httpx.ConnectError("no resuelve", request=request)

    result = await run_with(handler, make_site())

    assert result.is_up is False
    assert "ConnectError" in result.error


async def test_check_many_mantiene_el_orden():
    sites = [make_site(1), make_site(2), make_site(3)]

    transport = httpx.MockTransport(lambda req: httpx.Response(200))
    async with httpx.AsyncClient(transport=transport) as client:
        results = await check_many(client, sites)

    assert [r.site_id for r in results] == [1, 2, 3]
    