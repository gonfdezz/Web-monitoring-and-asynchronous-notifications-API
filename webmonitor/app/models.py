from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, Index, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SiteStatus(str, Enum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class MonitoredSite(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    url: str = Field(index=True)
    check_interval: int = 60
    is_active: bool = True

    # Estado actual (desnormalizado a propósito)
    status: SiteStatus = SiteStatus.UNKNOWN
    consecutive_failures: int = 0
    last_checked_at: datetime | None = None

    created_at: datetime = Field(default_factory=utcnow)

    logs: list["HealthLog"] = Relationship(
        back_populates="site",
        cascade_delete=True,
    )


class HealthLog(SQLModel, table=True):
    __table_args__ = (Index("ix_healthlog_site_checked", "site_id", "checked_at"),)

    id: int | None = Field(default=None, primary_key=True)
    site_id: int = Field(foreign_key="monitoredsite.id", ondelete="CASCADE")
    checked_at: datetime = Field(default_factory=utcnow)

    is_up: bool
    status_code: int | None = None
    response_time_ms: float | None = None
    error: str | None = None

    site: MonitoredSite | None = Relationship(back_populates="logs")