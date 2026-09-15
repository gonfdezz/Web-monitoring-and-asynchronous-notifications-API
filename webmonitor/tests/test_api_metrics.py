from datetime import datetime, timedelta, timezone

import pytest
from app.models import HealthLog, MonitoredSite
from tests.conftest import IS_POSTGRES


async def crear_sitio_con_logs(session, muestras):
    """muestras: lista de (is_up, latencia_ms)"""
    site = MonitoredSite(name="Test", url="https://test.com")
    session.add(site)
    await session.commit()
    await session.refresh(site)

    now = datetime.now(timezone.utc)
    for i, (is_up, ms) in enumerate(muestras):
        session.add(HealthLog(
            site_id=site.id,
            checked_at=now - timedelta(minutes=i),
            is_up=is_up,
            status_code=200 if is_up else None,
            response_time_ms=ms,
        ))
    await session.commit()
    return site


async def test_logs_ordenados_y_limitados(client, session):
    site = await crear_sitio_con_logs(session, [(True, 100.0)] * 5)

    r = await client.get(f"/sites/{site.id}/logs", params={"limit": 3})

    assert r.status_code == 200
    logs = r.json()
    assert len(logs) == 3
    assert logs[0]["checked_at"] > logs[1]["checked_at"]   # más reciente primero


async def test_logs_de_sitio_inexistente(client):
    assert (await client.get("/sites/9999/logs")).status_code == 404


@pytest.mark.postgres
@pytest.mark.skipif(not IS_POSTGRES, reason="percentile_cont solo existe en PostgreSQL")
async def test_metricas(client, session):
    site = await crear_sitio_con_logs(
        session,
        [(True, 100.0), (True, 200.0), (False, None), (True, 300.0)],
    )

    r = await client.get(f"/sites/{site.id}/metrics", params={"hours": 24})

    body = r.json()
    assert body["total_checks"] == 4
    assert body["successful_checks"] == 3
    assert body["uptime_percent"] == 75.0
    assert body["avg_response_time_ms"] == 200.0   # ← el None NO cuenta