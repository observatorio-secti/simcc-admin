import time
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from simcc_admin.database import get_session
from simcc_admin.models import Institution, UserRole
from simcc_admin.schemas import (
    GenericEnvelope,
    InstitutionCreate,
    InstitutionPublic,
    InstitutionUpdate,
    Message,
    Meta,
    Pagination,
    Sort,
)
from simcc_admin.security import RequireRole

router = APIRouter(
    prefix="/institutions",
    tags=["academic:institutions"],
    dependencies=[Depends(RequireRole(UserRole.ADMIN))],
)
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=GenericEnvelope[InstitutionPublic])
@router.get(
    "/", response_model=GenericEnvelope[InstitutionPublic], include_in_schema=False
)
async def list_institutions(
    session: Session,
    q: Annotated[str | None, Query(description="Busca por nome ou sigla")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    sort_by: Annotated[str, Query(pattern="^(name|acronym|created_at)$")] = "name",
    sort_order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
):
    start_time = time.perf_counter()

    query = select(Institution)
    count_query = select(func.count()).select_from(Institution)

    if q:
        search_filter = (Institution.name.ilike(f"%{q}%")) | (
            Institution.acronym.ilike(f"%{q}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_items = await session.scalar(count_query) or 0

    order_col = getattr(Institution, sort_by)
    query = query.order_by(
        order_col.desc() if sort_order == "desc" else order_col.asc()
    )

    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await session.scalars(query)
    institutions = result.all()

    took_ms = int((time.perf_counter() - start_time) * 1000)

    return GenericEnvelope[InstitutionPublic](
        data=institutions,
        pagination=Pagination.create(
            page=page, per_page=per_page, total_items=total_items
        ),
        filters_applied={"q": q, "page": page, "per_page": per_page},
        sort=Sort(by=sort_by, order=sort_order),
        meta=Meta(took_ms=took_ms, cached=False),
        facets=None,
        summary=None,
    )


@router.get("/{institution_id}", response_model=InstitutionPublic)
async def get_institution(institution_id: UUID, session: Session):
    institution = await session.scalar(
        select(Institution).where(Institution.id == institution_id)
    )
    if not institution:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Institution not found"
        )
    return institution


@router.post("", status_code=HTTPStatus.CREATED, response_model=InstitutionPublic)
@router.post(
    "/",
    status_code=HTTPStatus.CREATED,
    response_model=InstitutionPublic,
    include_in_schema=False,
)
async def create_institution(payload: InstitutionCreate, session: Session):
    existing = await session.scalar(
        select(Institution).where(
            (Institution.name == payload.name)
            | (Institution.acronym == payload.acronym)
        )
    )
    if existing:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Institution with this name or acronym already exists",
        )

    institution = Institution(name=payload.name, acronym=payload.acronym)
    session.add(institution)
    await session.commit()
    await session.refresh(institution)

    return institution


@router.put("/{institution_id}", response_model=InstitutionPublic)
async def update_institution(
    institution_id: UUID, payload: InstitutionUpdate, session: Session
):
    institution = await session.scalar(
        select(Institution).where(Institution.id == institution_id)
    )
    if not institution:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Institution not found"
        )

    try:
        institution.name = payload.name
        institution.acronym = payload.acronym
        await session.commit()
        await session.refresh(institution)
        return institution
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Institution with this name or acronym already exists",
        ) from e


@router.delete("/{institution_id}", response_model=Message)
async def delete_institution(institution_id: UUID, session: Session):
    institution = await session.scalar(
        select(Institution).where(Institution.id == institution_id)
    )
    if not institution:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Institution not found"
        )

    await session.delete(institution)
    await session.commit()

    return {"message": "Institution deleted"}
