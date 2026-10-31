import io
import time
from http import HTTPStatus
from typing import Annotated, Any
from uuid import UUID

import polars as pl
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from simcc_admin.database import get_session
from simcc_admin.models import (
    Collection,
    Institution,
    Researcher,
    ResearcherCollection,
    ResearcherInstitution,
    UserRole,
)
from simcc_admin.schemas import (
    Affiliation,
    CollectionMembership,
    CollectionRef,
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
from simcc_admin.security import RequireRole, RequireServiceTokenOrRole

router = APIRouter(
    prefix="/researchers",
    tags=["academic:researchers"],
)
Session = Annotated[AsyncSession, Depends(get_session)]

require_admin = Depends(RequireRole(UserRole.ADMIN))
require_service_or_admin = Depends(RequireServiceTokenOrRole(UserRole.ADMIN))


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


def _build_collections(
    links: list[ResearcherCollection],
) -> list[CollectionMembership]:
    valid_links = [link for link in links if link.collection is not None]
    valid_links.sort(key=lambda x: x.collection.name)
    return [
        CollectionMembership(
            collection=CollectionRef.model_validate(link.collection),
            attributes=link.attributes or {},
            created_at=link.created_at,
        )
        for link in valid_links
    ]


@router.get(
    "/export/parquet",
    dependencies=[require_service_or_admin],
    summary="Exporta lattes_id dos pesquisadores em formato Parquet",
)
async def export_researchers_parquet(
    session: Session,
    collection: Annotated[str | None, Query(description="Filtrar por slug da coleção")] = None,
) -> Response:
    stmt = (
        select(
            Researcher.lattes_id,
            func.coalesce(func.min(Collection.refresh_interval_days), 1).label(
                "refresh_interval_days"
            ),
        )
        .outerjoin(
            ResearcherCollection,
            ResearcherCollection.researcher_id == Researcher.id,
        )
        .outerjoin(
            Collection,
            Collection.id == ResearcherCollection.collection_id,
        )
        .where(
            Researcher.lattes_id.is_not(None),
            func.trim(Researcher.lattes_id) != "",
        )
    )

    if collection and collection.strip():
        stmt = stmt.where(Collection.slug == collection.strip())

    stmt = stmt.group_by(Researcher.lattes_id).order_by(Researcher.lattes_id)
    result = await session.execute(stmt)
    rows = result.all()

    lattes_ids = [row[0] for row in rows]
    refresh_intervals = [int(row[1]) for row in rows]

    df = pl.DataFrame(
        {
            "lattes_id": lattes_ids,
            "refresh_interval_days": refresh_intervals,
        }
    )
    buf = io.BytesIO()
    df.write_parquet(buf, compression="zstd")

    return Response(
        content=buf.getvalue(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": 'attachment; filename="researchers.parquet"'
        },
    )


@router.get("", response_model=ResearcherSearchResponse, dependencies=[require_admin])
@router.get(
    "/",
    response_model=ResearcherSearchResponse,
    include_in_schema=False,
    dependencies=[require_admin],
)
async def search_researchers(
    session: Session,
    q: Annotated[str | None, Query(description="Busca por nome ou lattes_id")] = None,
    institution_id: Annotated[
        UUID | None, Query(description="Filtro por instituição")
    ] = None,
    collection_id: Annotated[
        UUID | None, Query(description="Filtro por coleção")
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
        ),
        selectinload(Researcher.collections).selectinload(
            ResearcherCollection.collection
        ),
    )
    count_query = select(func.count(Researcher.id)).select_from(Researcher)

    if institution_id:
        inst_filter = (
            select(1)
            .select_from(ResearcherInstitution)
            .where(
                ResearcherInstitution.researcher_id == Researcher.id,
                ResearcherInstitution.institution_id == institution_id,
            )
            .exists()
        )
        query = query.where(inst_filter)
        count_query = count_query.where(inst_filter)

    if collection_id:
        coll_filter = (
            select(1)
            .select_from(ResearcherCollection)
            .where(
                ResearcherCollection.researcher_id == Researcher.id,
                ResearcherCollection.collection_id == collection_id,
            )
            .exists()
        )
        query = query.where(coll_filter)
        count_query = count_query.where(coll_filter)

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
            collections=_build_collections(r.collections),
        )
        for r in researchers
    ]

    return ResearcherSearchResponse(
        data=items,
        pagination=Pagination.create(
            page=page, per_page=per_page, total_items=total_items
        ),
        filters_applied=FiltersApplied(
            q=q, institution_id=institution_id, collection_id=collection_id
        ),
        sort=Sort(by=sort_by, order=sort_order),
        meta=Meta(took_ms=took_ms, cached=False),
        facets=None,
        summary=None,
    )


@router.get(
    "/{researcher_id}",
    response_model=ResearcherDetail,
    dependencies=[require_admin],
)
async def get_researcher(researcher_id: UUID, session: Session):
    query = (
        select(Researcher)
        .options(
            selectinload(Researcher.institutions).selectinload(
                ResearcherInstitution.institution
            ),
            selectinload(Researcher.collections).selectinload(
                ResearcherCollection.collection
            ),
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
        collections=_build_collections(researcher.collections),
    )


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    response_model=ResearcherDetail,
    dependencies=[require_admin],
)
@router.post(
    "/",
    status_code=HTTPStatus.CREATED,
    response_model=ResearcherDetail,
    include_in_schema=False,
    dependencies=[require_admin],
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

    # Validação de coleções antes de salvar qualquer registro
    target_collections: list[Collection] = []
    if payload.collection_ids:
        for col_id in payload.collection_ids:
            col = await session.scalar(
                select(Collection).where(Collection.id == col_id)
            )
            if not col:
                raise HTTPException(
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    detail=f"Collection {col_id} not found",
                )
            target_collections.append(col)
    else:
        default_col = await session.scalar(
            select(Collection).where(Collection.is_default.is_(True))
        )
        if not default_col:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail="No default collection configured",
            )
        target_collections.append(default_col)

    researcher = Researcher(name=payload.name, lattes_id=payload.lattes_id)
    session.add(researcher)
    await session.flush()

    # Vincula coleções
    for col in target_collections:
        col_link = ResearcherCollection(
            researcher_id=researcher.id,
            collection_id=col.id,
            attributes={},
        )
        session.add(col_link)

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
    return await get_researcher(researcher.id, session)


@router.put(
    "/{researcher_id}",
    response_model=ResearcherDetail,
    dependencies=[require_admin],
)
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


@router.delete(
    "/{researcher_id}",
    response_model=Message,
    dependencies=[require_admin],
)
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


# --- Rotas de Gerenciamento de Vínculos Institucionais (Affiliations) ---


@router.post(
    "/{researcher_id}/institutions/{institution_id}",
    status_code=HTTPStatus.CREATED,
    response_model=Affiliation,
    dependencies=[require_admin],
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


@router.delete(
    "/{researcher_id}/institutions/{institution_id}",
    response_model=Message,
    dependencies=[require_admin],
)
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


# --- Rotas de Gerenciamento de Pertencimento a Coleções (Collections) ---


@router.post(
    "/{researcher_id}/collections/{collection_id}",
    status_code=HTTPStatus.CREATED,
    response_model=CollectionMembership,
    dependencies=[require_admin],
)
async def add_researcher_to_collection(
    researcher_id: UUID,
    collection_id: UUID,
    session: Session,
    payload: Annotated[dict[str, Any] | None, Body()] = None,
):
    attrs = payload or {}
    researcher = await session.scalar(
        select(Researcher).where(Researcher.id == researcher_id)
    )
    if not researcher:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Researcher not found"
        )

    collection = await session.scalar(
        select(Collection).where(Collection.id == collection_id)
    )
    if not collection:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Collection not found"
        )

    existing = await session.scalar(
        select(ResearcherCollection).where(
            ResearcherCollection.researcher_id == researcher_id,
            ResearcherCollection.collection_id == collection_id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Researcher already belongs to this collection",
        )

    attributes = attrs.get("attributes", {}) if isinstance(attrs, dict) else {}
    link = ResearcherCollection(
        researcher_id=researcher_id,
        collection_id=collection_id,
        attributes=attributes,
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)

    return CollectionMembership(
        collection=CollectionRef.model_validate(collection),
        attributes=link.attributes or {},
        created_at=link.created_at,
    )


@router.put(
    "/{researcher_id}/collections/{collection_id}",
    response_model=CollectionMembership,
    dependencies=[require_admin],
)
async def update_researcher_collection_attributes(
    researcher_id: UUID,
    collection_id: UUID,
    session: Session,
    payload: Annotated[dict[str, Any] | None, Body()] = None,
):
    attrs = payload or {}
    link = await session.scalar(
        select(ResearcherCollection)
        .options(selectinload(ResearcherCollection.collection))
        .where(
            ResearcherCollection.researcher_id == researcher_id,
            ResearcherCollection.collection_id == collection_id,
        )
    )
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Researcher does not belong to this collection",
        )

    attributes = attrs.get("attributes", {}) if isinstance(attrs, dict) else {}
    link.attributes = attributes
    await session.commit()
    await session.refresh(link)

    return CollectionMembership(
        collection=CollectionRef.model_validate(link.collection),
        attributes=link.attributes or {},
        created_at=link.created_at,
    )


@router.delete(
    "/{researcher_id}/collections/{collection_id}",
    response_model=Message,
    dependencies=[require_admin],
)
async def remove_researcher_from_collection(
    researcher_id: UUID, collection_id: UUID, session: Session
):
    link = await session.scalar(
        select(ResearcherCollection).where(
            ResearcherCollection.researcher_id == researcher_id,
            ResearcherCollection.collection_id == collection_id,
        )
    )
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Researcher does not belong to this collection",
        )

    await session.delete(link)
    await session.commit()

    return {"message": "Collection membership removed"}
