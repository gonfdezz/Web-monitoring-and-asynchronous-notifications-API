from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models import SiteStatus


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: HttpUrl
    check_interval: int = Field(default=60, ge=15, le=86400)


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    check_interval: int | None = Field(default=None, ge=15, le=86400)
    is_active: bool | None = None


class SiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    check_interval: int
    is_active: bool
    status: SiteStatus
    consecutive_failures: int
    last_checked_at: datetime | None
    created_at: datetime


class HealthLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    checked_at: datetime
    is_up: bool
    status_code: int | None
    response_time_ms: float | None
    error: str | None


class SiteMetrics(BaseModel):
    site_id: int
    window_hours: int
    total_checks: int
    successful_checks: int
    uptime_percent: float
    avg_response_time_ms: float | None
    p95_response_time_ms: float | None