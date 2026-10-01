import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from simcc_admin.database import get_session
from simcc_admin.models import Researcher, ResearcherInstitution
from simcc_admin.schemas import (
    FiltersApplied,
    Meta,
    Pagination,
    ResearcherItem,
    ResearcherSearchResponse,
    Sort,
)

router = APIRouter(prefix="/researchers", tags=["academic:researchers"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=ResearcherSearchResponse)
@router.get("/", response_model=ResearcherSearchResponse, include_in_schema=False)
async def search_researchers(
    session: Session,
    q: Annotated[str | None, Query(description="Busca por nome ou lattes_id")] = None,
    institution_id: Annotated[
        UUID | None, Query(description="Filtro por instituição")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    sort_by: Annotated[str, Query(pattern="^(name|lattes_id|created_at)$")] = "name",
    sort_order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
):
    start_time = time.perf_counter()

    query = select(Researcher)
    count_query = select(func.count(func.distinct(Researcher.id))).select_from(
        Researcher
    )

    if institution_id:
        query = query.join(ResearcherInstitution).where(
            ResearcherInstitution.institution_id == institution_id
        )
        count_query = count_query.join(ResearcherInstitution).where(
            ResearcherInstitution.institution_id == institution_id
        )

    if q:
        search_filter = (Researcher.name.ilike(f"%{q}%")) | (
            Researcher.lattes_id.ilike(f"%{q}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_items = await session.scalar(count_query) or 0

    order_col = getattr(Researcher, sort_by)
    query = query.order_by(
        order_col.desc() if sort_order == "desc" else order_col.asc()
    )

    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await session.scalars(query)
    researchers = result.all()

    took_ms = int((time.perf_counter() - start_time) * 1000)

    items = [
        ResearcherItem(
            researcher_id=r.id,
            name=r.name,
            lattes_id=r.lattes_id,
            created_at=r.created_at,
        )
        for r in researchers
    ]

    return ResearcherSearchResponse(
        data=items,
        pagination=Pagination.create(
            page=page, per_page=per_page, total_items=total_items
        ),
        filters_applied=FiltersApplied(q=q, institution_id=institution_id),
        sort=Sort(by=sort_by, order=sort_order),
        meta=Meta(took_ms=took_ms, cached=False),
        facets=None,
        summary=None,
    )
