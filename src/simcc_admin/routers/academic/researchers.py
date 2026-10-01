import time
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from simcc_admin.database import get_session
from simcc_admin.models import (
    Institution,
    Researcher,
    ResearcherInstitution,
    UserRole,
)
from simcc_admin.schemas import (
    Affiliation,
    FiltersApplied,
    InstitutionRef,
    Message,
    Meta,
    Pagination,
    ResearcherCreate,
    ResearcherDetail,
    ResearcherItem,
    ResearcherSearchResponse,
    ResearcherUpdate,
    Sort,
)
from simcc_admin.security import RequireRole

router = APIRouter(
    prefix="/researchers",
    tags=["academic:researchers"],
    dependencies=[Depends(RequireRole(UserRole.ADMIN))],
)
Session = Annotated[AsyncSession, Depends(get_session)]


def _build_affiliations(
    links: list[ResearcherInstitution],
) -> list[Affiliation]:
    return [
        Affiliation(
            institution=InstitutionRef.model_validate(link.institution),
            created_at=link.created_at,
        )
        for link in links
        if link.institution is not None
    ]


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

    query = select(Researcher).options(
        selectinload(Researcher.institutions).selectinload(
            ResearcherInstitution.institution
        )
    )
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
    researchers = result.unique().all()

    took_ms = int((time.perf_counter() - start_time) * 1000)

    items = [
        ResearcherItem(
            researcher_id=r.id,
            name=r.name,
            lattes_id=r.lattes_id,
            created_at=r.created_at,
            affiliations=_build_affiliations(r.institutions),
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


@router.get("/{researcher_id}", response_model=ResearcherDetail)
async def get_researcher(researcher_id: UUID, session: Session):
    query = (
        select(Researcher)
        .options(
            selectinload(Researcher.institutions).selectinload(
                ResearcherInstitution.institution
            )
        )
        .where(Researcher.id == researcher_id)
    )
    researcher = await session.scalar(query)
    if not researcher:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Researcher not found"
        )

    return ResearcherDetail(
        researcher_id=researcher.id,
        name=researcher.name,
        lattes_id=researcher.lattes_id,
        created_at=researcher.created_at,
        affiliations=_build_affiliations(researcher.institutions),
    )


@router.post("", status_code=HTTPStatus.CREATED, response_model=ResearcherDetail)
@router.post(
    "/",
    status_code=HTTPStatus.CREATED,
    response_model=ResearcherDetail,
    include_in_schema=False,
)
async def create_researcher(payload: ResearcherCreate, session: Session):
    existing = await session.scalar(
        select(Researcher).where(Researcher.lattes_id == payload.lattes_id)
    )
    if existing:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Researcher with this Lattes ID already exists",
        )

    researcher = Researcher(name=payload.name, lattes_id=payload.lattes_id)
    session.add(researcher)
    await session.flush()

    # Vincula instituições caso enviadas
    for inst_id in payload.institution_ids:
        inst = await session.scalar(
            select(Institution).where(Institution.id == inst_id)
        )
        if inst:
            link = ResearcherInstitution(
                researcher_id=researcher.id, institution_id=inst.id
            )
            session.add(link)

    await session.commit()

    # Recarrega com relacionamentos
    return await get_researcher(researcher.id, session)


@router.put("/{researcher_id}", response_model=ResearcherDetail)
async def update_researcher(
    researcher_id: UUID, payload: ResearcherUpdate, session: Session
):
    researcher = await session.scalar(
        select(Researcher).where(Researcher.id == researcher_id)
    )
    if not researcher:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Researcher not found"
        )

    try:
        researcher.name = payload.name
        researcher.lattes_id = payload.lattes_id
        await session.commit()
        return await get_researcher(researcher.id, session)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Researcher with this Lattes ID already exists",
        ) from e


@router.delete("/{researcher_id}", response_model=Message)
async def delete_researcher(researcher_id: UUID, session: Session):
    researcher = await session.scalar(
        select(Researcher).where(Researcher.id == researcher_id)
    )
    if not researcher:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Researcher not found"
        )

    await session.delete(researcher)
    await session.commit()

    return {"message": "Researcher deleted"}


# --- Rotas de Gerenciamento de Vínculos (Affiliations) ---


@router.post(
    "/{researcher_id}/institutions/{institution_id}",
    status_code=HTTPStatus.CREATED,
    response_model=Affiliation,
)
async def add_affiliation(researcher_id: UUID, institution_id: UUID, session: Session):
    researcher = await session.scalar(
        select(Researcher).where(Researcher.id == researcher_id)
    )
    if not researcher:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Researcher not found"
        )

    institution = await session.scalar(
        select(Institution).where(Institution.id == institution_id)
    )
    if not institution:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Institution not found"
        )

    existing_link = await session.scalar(
        select(ResearcherInstitution).where(
            ResearcherInstitution.researcher_id == researcher_id,
            ResearcherInstitution.institution_id == institution_id,
        )
    )
    if existing_link:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Affiliation already exists",
        )

    link = ResearcherInstitution(
        researcher_id=researcher_id, institution_id=institution_id
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)

    return Affiliation(
        institution=InstitutionRef.model_validate(institution),
        created_at=link.created_at,
    )


@router.delete("/{researcher_id}/institutions/{institution_id}", response_model=Message)
async def remove_affiliation(
    researcher_id: UUID, institution_id: UUID, session: Session
):
    link = await session.scalar(
        select(ResearcherInstitution).where(
            ResearcherInstitution.researcher_id == researcher_id,
            ResearcherInstitution.institution_id == institution_id,
        )
    )
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Affiliation not found"
        )

    await session.delete(link)
    await session.commit()

    return {"message": "Affiliation removed"}
