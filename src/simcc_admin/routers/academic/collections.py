import time
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from simcc_admin.database import get_session
from simcc_admin.models import Collection, ResearcherCollection, UserRole
from simcc_admin.schemas import (
    CollectionCreate,
    CollectionPublic,
    CollectionUpdate,
    GenericEnvelope,
    Message,
    Meta,
    Pagination,
    Sort,
)
from simcc_admin.security import RequireRole

router = APIRouter(
    prefix="/collections",
    tags=["academic:collections"],
    dependencies=[Depends(RequireRole(UserRole.ADMIN))],
)
Session = Annotated[AsyncSession, Depends(get_session)]


def _subquery_member_count():
    return (
        select(func.count(ResearcherCollection.id))
        .where(ResearcherCollection.collection_id == Collection.id)
        .scalar_subquery()
    )


@router.get("", response_model=GenericEnvelope[CollectionPublic])
@router.get(
    "/", response_model=GenericEnvelope[CollectionPublic], include_in_schema=False
)
async def list_collections(
    session: Session,
    q: Annotated[str | None, Query(description="Busca por nome ou slug")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    sort_by: Annotated[str, Query(pattern="^(name|slug|created_at)$")] = "name",
    sort_order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
):
    start_time = time.perf_counter()

    member_count_subq = _subquery_member_count().label("researcher_count")

    query = select(Collection, member_count_subq)
    count_query = select(func.count()).select_from(Collection)

    if q:
        search_filter = (Collection.name.ilike(f"%{q}%")) | (
            Collection.slug.ilike(f"%{q}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_items = await session.scalar(count_query) or 0

    order_col = getattr(Collection, sort_by)
    query = query.order_by(
        order_col.desc() if sort_order == "desc" else order_col.asc()
    )

    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await session.execute(query)
    rows = result.all()

    items = [
        CollectionPublic(
            id=col.id,
            slug=col.slug,
            name=col.name,
            description=col.description,
            refresh_interval_days=col.refresh_interval_days,
            is_default=col.is_default,
            created_at=col.created_at,
            researcher_count=count or 0,
        )
        for col, count in rows
    ]

    took_ms = int((time.perf_counter() - start_time) * 1000)

    return GenericEnvelope[CollectionPublic](
        data=items,
        pagination=Pagination.create(
            page=page, per_page=per_page, total_items=total_items
        ),
        filters_applied={"q": q, "page": page, "per_page": per_page},
        sort=Sort(by=sort_by, order=sort_order),
        meta=Meta(took_ms=took_ms, cached=False),
        facets=None,
        summary=None,
    )


@router.get("/{collection_id}", response_model=CollectionPublic)
async def get_collection(collection_id: UUID, session: Session):
    member_count_subq = _subquery_member_count().label("researcher_count")
    query = select(Collection, member_count_subq).where(
        Collection.id == collection_id
    )
    result = await session.execute(query)
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Collection not found"
        )
    col, count = row
    return CollectionPublic(
        id=col.id,
        slug=col.slug,
        name=col.name,
        description=col.description,
        refresh_interval_days=col.refresh_interval_days,
        is_default=col.is_default,
        created_at=col.created_at,
        researcher_count=count or 0,
    )


@router.post("", status_code=HTTPStatus.CREATED, response_model=CollectionPublic)
@router.post(
    "/",
    status_code=HTTPStatus.CREATED,
    response_model=CollectionPublic,
    include_in_schema=False,
)
async def create_collection(payload: CollectionCreate, session: Session):
    existing = await session.scalar(
        select(Collection).where(
            (Collection.slug == payload.slug) | (Collection.name == payload.name)
        )
    )
    if existing:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Collection with this slug or name already exists",
        )

    col = Collection(
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        refresh_interval_days=payload.refresh_interval_days,
        is_default=False,
    )
    session.add(col)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Collection with this slug or name already exists",
        ) from e

    await session.refresh(col)
    return CollectionPublic(
        id=col.id,
        slug=col.slug,
        name=col.name,
        description=col.description,
        refresh_interval_days=col.refresh_interval_days,
        is_default=col.is_default,
        created_at=col.created_at,
        researcher_count=0,
    )


@router.put("/{collection_id}", response_model=CollectionPublic)
async def update_collection(
    collection_id: UUID, payload: CollectionUpdate, session: Session
):
    col = await session.scalar(
        select(Collection).where(Collection.id == collection_id)
    )
    if not col:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Collection not found"
        )

    if payload.is_default is True and not col.is_default:
        await session.execute(
            update(Collection)
            .where(Collection.is_default.is_(True))
            .values(is_default=False)
        )
        col.is_default = True
    elif payload.is_default is False and col.is_default:
        col.is_default = False

    if payload.name is not None:
        col.name = payload.name
    if payload.description is not None:
        col.description = payload.description
    if payload.refresh_interval_days is not None:
        col.refresh_interval_days = payload.refresh_interval_days

    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Collection with this name already exists",
        ) from e

    return await get_collection(collection_id, session)


@router.delete("/{collection_id}", response_model=Message)
async def delete_collection(collection_id: UUID, session: Session):
    col = await session.scalar(
        select(Collection).where(Collection.id == collection_id)
    )
    if not col:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Collection not found"
        )

    if col.is_default:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Cannot delete default collection",
        )

    member_count = await session.scalar(
        select(func.count()).select_from(ResearcherCollection).where(
            ResearcherCollection.collection_id == collection_id
        )
    )
    if member_count and member_count > 0:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Cannot delete collection with associated researchers",
        )

    await session.delete(col)
    await session.commit()

    return {"message": "Collection deleted"}
