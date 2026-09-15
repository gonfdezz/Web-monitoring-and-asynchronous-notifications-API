import httpx
import pytest
from app.config import settings
from app.models import MonitoredSite, SiteStatus
from app.services.checker import CheckResult
from app.services.notifier import send_alert


@pytest.fixture
def site():
    return MonitoredSite(id=1, name="Test", url="https://test.com", status=SiteStatus.DOWN)


async def test_no_envia_si_no_hay_webhook(monkeypatch, site):
    monkeypatch.setattr(settings, "discord_webhook_url", None)

    async with httpx.AsyncClient() as client:
        enviado = await send_alert(client, site, CheckResult(site_id=1, is_up=False), "down")

    assert enviado is False


async def test_envia_payload_correcto(monkeypatch, site):
    monkeypatch.setattr(settings, "discord_webhook_url", "https://discord.test/webhook")
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["url"] = str(request.url)
        capturado["body"] = request.read().decode()
        return httpx.Response(204)

    transport = httpx.MockTransport(handler)
    result = CheckResult(site_id=1, is_up=False, error="Connection refused")

    async with httpx.AsyncClient(transport=transport) as client:
        enviado = await send_alert(client, site, result, "down")

    assert enviado is True
    assert capturado["url"] == "https://discord.test/webhook"
    assert "Test" in capturado["body"]
    assert "Connection refused" in capturado["body"]


async def test_fallo_de_discord_no_rompe(monkeypatch, site):
    monkeypatch.setattr(settings, "discord_webhook_url", "https://discord.test/webhook")

    transport = httpx.MockTransport(lambda req: httpx.Response(500))

    async with httpx.AsyncClient(transport=transport) as client:
        enviado = await send_alert(client, site, CheckResult(site_id=1, is_up=False), "down")

    assert enviado is False      # degrada, no explota