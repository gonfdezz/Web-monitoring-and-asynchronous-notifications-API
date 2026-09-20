from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_session
from app.models import MonitoredSite
from app.schemas import SiteCreate, SiteRead, SiteUpdate
from app.security import require_api_key

router = APIRouter(prefix="/sites", tags=["sites"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _get_or_404(session: AsyncSession, site_id: int) -> MonitoredSite:
    site = await session.get(MonitoredSite, site_id)
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el sitio {site_id}",
        )
    return site


@router.post(
    "",
    response_model=SiteRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def create_site(payload: SiteCreate, session: SessionDep):
    site = MonitoredSite(
        name=payload.name,
        url=str(payload.url),
        check_interval=payload.check_interval,
    )
    session.add(site)
    await session.commit()
    await session.refresh(site)
    return site


@router.get("", response_model=list[SiteRead])
async def list_sites(
    session: SessionDep,
    only_active: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(MonitoredSite).order_by(MonitoredSite.id).limit(limit).offset(offset)
    if only_active:
        stmt = stmt.where(MonitoredSite.is_active.is_(True))
    return (await session.execute(stmt)).scalars().all()


@router.get("/{site_id}", response_model=SiteRead)
async def get_site(site_id: int, session: SessionDep):
    return await _get_or_404(session, site_id)


@router.patch(
    "/{site_id}",
    response_model=SiteRead,
    dependencies=[Depends(require_api_key)],
)
async def update_site(site_id: int, payload: SiteUpdate, session: SessionDep):
    site = await _get_or_404(session, site_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(site, field, value)
    await session.commit()
    await session.refresh(site)
    return site


@router.delete(
    "/{site_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
async def delete_site(site_id: int, session: SessionDep):
    site = await _get_or_404(session, site_id)
    await session.delete(site)
    await session.commit()