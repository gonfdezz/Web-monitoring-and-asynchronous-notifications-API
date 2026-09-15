import pytest
from app.models import MonitoredSite, SiteStatus


async def test_crear_sitio(client):
    r = await client.post("/sites", json={"name": "Python", "url": "https://python.org"})

    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Python"
    assert body["status"] == "unknown"
    assert body["check_interval"] == 60
    assert "id" in body


async def test_no_se_puede_falsear_el_estado(client):
    """Overposting: los campos internos se ignoran."""
    r = await client.post(
        "/sites",
        json={"name": "X", "url": "https://x.com", "status": "up", "consecutive_failures": 99},
    )

    assert r.status_code == 201
    assert r.json()["status"] == "unknown"
    assert r.json()["consecutive_failures"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "X", "url": "no soy una url"},
        {"name": "", "url": "https://x.com"},
        {"name": "X", "url": "https://x.com", "check_interval": 5},
        {"url": "https://x.com"},
    ],
)
async def test_validacion_rechaza(client, payload):
    r = await client.post("/sites", json=payload)
    assert r.status_code == 422


async def test_listar_y_paginar(client):
    for i in range(3):
        await client.post("/sites", json={"name": f"S{i}", "url": f"https://s{i}.com"})

    r = await client.get("/sites", params={"limit": 2})
    assert len(r.json()) == 2

    r = await client.get("/sites", params={"limit": 2, "offset": 2})
    assert len(r.json()) == 1


async def test_patch_parcial_no_borra_campos(client):
    creado = (await client.post("/sites", json={"name": "Original", "url": "https://x.com"})).json()

    r = await client.patch(f"/sites/{creado['id']}", json={"check_interval": 300})

    assert r.status_code == 200
    assert r.json()["check_interval"] == 300
    assert r.json()["name"] == "Original"      # ← exclude_unset funcionando


async def test_borrar(client):
    creado = (await client.post("/sites", json={"name": "X", "url": "https://x.com"})).json()

    assert (await client.delete(f"/sites/{creado['id']}")).status_code == 204
    assert (await client.get(f"/sites/{creado['id']}")).status_code == 404


async def test_404_en_sitio_inexistente(client):
    assert (await client.get("/sites/9999")).status_code == 404