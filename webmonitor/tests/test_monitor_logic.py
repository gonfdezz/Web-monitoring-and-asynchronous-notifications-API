from datetime import UTC, datetime, timedelta

import pytest

from app.models import MonitoredSite, SiteStatus
from app.services.checker import CheckResult
from app.services.monitor import apply_result, is_due


def make_site(**overrides) -> MonitoredSite:
    defaults = {
        "id": 1,
        "name": "Test",
        "url": "https://test.com",
        "check_interval": 60,
        "status": SiteStatus.UNKNOWN,
        "consecutive_failures": 0,
    }
    return MonitoredSite(**{**defaults, **overrides})


def ok() -> CheckResult:
    return CheckResult(site_id=1, is_up=True, status_code=200, response_time_ms=50.0)


def fail() -> CheckResult:
    return CheckResult(site_id=1, is_up=False, error="Connection refused")


@pytest.mark.parametrize(
    "previous, failures, result, expected_status, expected_alert",
    [
        (SiteStatus.UNKNOWN, 0, ok(),   SiteStatus.UP,      None),
        (SiteStatus.UP,      0, ok(),   SiteStatus.UP,      None),
        (SiteStatus.UP,      0, fail(), SiteStatus.UP,      None),   # 1er fallo
        (SiteStatus.UP,      2, fail(), SiteStatus.DOWN,    "down"), # 3er fallo
        (SiteStatus.DOWN,    5, fail(), SiteStatus.DOWN,    None),   # ya avisado
        (SiteStatus.DOWN,    5, ok(),   SiteStatus.UP,      "recovered"),
    ],
)
def test_maquina_de_estados(previous, failures, result, expected_status, expected_alert):
    site = make_site(status=previous, consecutive_failures=failures)

    alert = apply_result(site, result)

    assert site.status == expected_status
    assert alert == expected_alert


def test_exito_resetea_contador():
    site = make_site(status=SiteStatus.UP, consecutive_failures=2)
    apply_result(site, ok())
    assert site.consecutive_failures == 0


def test_is_due_sin_comprobaciones_previas():
    assert is_due(make_site(last_checked_at=None), datetime.now(UTC)) is True


def test_is_due_respeta_el_intervalo():
    now = datetime.now(UTC)
    site = make_site(check_interval=60, last_checked_at=now - timedelta(seconds=30))
    assert is_due(site, now) is False


def test_is_due_cuando_vence():
    now = datetime.now(UTC)
    site = make_site(check_interval=60, last_checked_at=now - timedelta(seconds=61))
    assert is_due(site, now) is True