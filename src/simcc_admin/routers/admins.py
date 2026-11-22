import time
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from simcc_admin.database import get_session
from simcc_admin.models import Admin
from simcc_admin.schemas import (
    AdminCreate,
    AdminPublic,
    ErrorDetail,
    GenericEnvelope,
    Meta,
    Pagination,
    Sort,
)
from simcc_admin.security import AdminUser, require_admin

router = APIRouter(
    prefix="/admins",
    tags=["admins"],
    responses={
        401: {"model": ErrorDetail},
        403: {"model": ErrorDetail},
    },
)
Session = Annotated[AsyncSession, Depends(get_session)]
admin_dep = Depends(require_admin)


@router.get(
    "",
    response_model=GenericEnvelope[AdminPublic],
    dependencies=[admin_dep],
    summary="Lista administradores cadastrados",
)
@router.get(
    "/",
    response_model=GenericEnvelope[AdminPublic],
    dependencies=[admin_dep],
    include_in_schema=False,
)
async def list_admins(
    session: Session,
    q: Annotated[str | None, Query(description="Busca por nome, e-mail ou sub")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> GenericEnvelope[AdminPublic]:
    start_time = time.perf_counter()

    query = select(Admin)
    count_query = select(func.count()).select_from(Admin)

    if q and q.strip():
        pattern = f"%{q.strip()}%"
        search_filter = or_(
            Admin.name.ilike(pattern),
            Admin.email.ilike(pattern),
            Admin.sub.ilike(pattern),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_items = await session.scalar(count_query) or 0
    offset = (page - 1) * per_page
    query = query.order_by(Admin.created_at.desc()).offset(offset).limit(per_page)

    admins = list((await session.scalars(query)).all())
    took_ms = int((time.perf_counter() - start_time) * 1000)

    return GenericEnvelope[AdminPublic](
        data=[AdminPublic.model_validate(a) for a in admins],
        pagination=Pagination.create(
            page=page, per_page=per_page, total_items=total_items
        ),
        filters_applied={"q": q, "page": page, "per_page": per_page},
        sort=Sort(by="created_at", order="desc"),
        meta=Meta(took_ms=took_ms, cached=False),
    )


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    response_model=AdminPublic,
    responses={409: {"model": ErrorDetail}},
    summary="Cadastra um novo administrador por sub",
)
@router.post(
    "/",
    status_code=HTTPStatus.CREATED,
    response_model=AdminPublic,
    include_in_schema=False,
)
async def create_admin(
    payload: AdminCreate,
    session: Session,
    current_user: AdminUser,
) -> AdminPublic:
    sub = payload.sub.strip()
    if not sub:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="sub cannot be empty",
        )

    existing = await session.scalar(select(Admin).where(Admin.sub == sub))
    if existing is not None:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Admin with this sub already exists",
        )

    admin = Admin(
        sub=sub,
        name=payload.name.strip() if payload.name else None,
        email=payload.email.strip() if payload.email else None,
        created_by=current_user.sub,
    )
    session.add(admin)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Admin with this sub already exists",
        )
    await session.refresh(admin)
    return AdminPublic.model_validate(admin)


@router.delete(
    "/{admin_id}",
    status_code=HTTPStatus.NO_CONTENT,
    responses={
        404: {"model": ErrorDetail},
        409: {"model": ErrorDetail},
    },
    summary="Remove um administrador",
)
async def delete_admin(
    admin_id: UUID,
    session: Session,
    current_user: AdminUser,
) -> Response:
    admin = await session.scalar(select(Admin).where(Admin.id == admin_id))
    if admin is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Admin not found",
        )

    if admin.sub == current_user.sub:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Cannot remove yourself from admins",
        )

    total_admins = await session.scalar(select(func.count()).select_from(Admin)) or 0
    if total_admins <= 1:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Cannot remove the last admin",
        )

    await session.delete(admin)
    await session.commit()
    return Response(status_code=HTTPStatus.NO_CONTENT)
