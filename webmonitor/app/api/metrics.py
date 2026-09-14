from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.models import HealthLog, MonitoredSite
from app.schemas import HealthLogRead, SiteMetrics

router = APIRouter(prefix="/sites/{site_id}", tags=["metrics"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _ensure_site(session: AsyncSession, site_id: int) -> None:
    if await session.get(MonitoredSite, site_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No existe el sitio {site_id}")


@router.get("/metrics", response_model=SiteMetrics)
async def site_metrics(
    site_id: int,
    session: SessionDep,
    hours: Annotated[int, Query(ge=1, le=720)] = 24,
):
    await _ensure_site(session, site_id)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    stmt = select(
        func.count(HealthLog.id).label("total"),
        func.count(case((HealthLog.is_up.is_(True), 1))).label("ok"),
        func.avg(HealthLog.response_time_ms).label("avg_ms"),
        func.percentile_cont(0.95)
        .within_group(HealthLog.response_time_ms.asc())
        .label("p95_ms"),
    ).where(HealthLog.site_id == site_id, HealthLog.checked_at >= since)

    row = (await session.execute(stmt)).one()

    return SiteMetrics(
        site_id=site_id,
        window_hours=hours,
        total_checks=row.total,
        successful_checks=row.ok,
        uptime_percent=round(row.ok / row.total * 100, 2) if row.total else 0.0,
        avg_response_time_ms=round(row.avg_ms, 2) if row.avg_ms is not None else None,
        p95_response_time_ms=round(row.p95_ms, 2) if row.p95_ms is not None else None,
    )


@router.get("/logs", response_model=list[HealthLogRead])
async def site_logs(
    site_id: int,
    session: SessionDep,
    hours: Annotated[int, Query(ge=1, le=720)] = 24,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
):
    await _ensure_site(session, site_id)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    stmt = (
        select(HealthLog)
        .where(HealthLog.site_id == site_id, HealthLog.checked_at >= since)
        .order_by(HealthLog.checked_at.desc())
        .limit(limit)
    )
    return (await session.execute(stmt)).scalars().all()