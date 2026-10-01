import time
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from simcc_admin.database import get_session
from simcc_admin.models import User
from simcc_admin.schemas import (
    GenericEnvelope,
    Message,
    Meta,
    Pagination,
    Sort,
    UserPublic,
    UserSchema,
)
from simcc_admin.security import (
    get_current_user,
    get_password_hash,
)

router = APIRouter(prefix="/users", tags=["users"])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/", status_code=HTTPStatus.CREATED, response_model=UserPublic)
async def create_user(user: UserSchema, session: Session):
    db_user = await session.scalar(
        select(User).where(
            (User.username == user.username) | (User.email == user.email)
        )
    )

    if db_user:
        if db_user.username == user.username:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail="Username already exists",
            )
        elif db_user.email == user.email:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail="Email already exists",
            )

    hashed_password = get_password_hash(user.password)

    db_user = User(
        email=user.email,
        username=user.username,
        password=hashed_password,
    )

    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)

    return db_user


@router.get("/", response_model=GenericEnvelope[UserPublic])
async def read_users(
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 10,
):
    start_time = time.perf_counter()
    offset = (page - 1) * per_page

    total_items = await session.scalar(select(func.count()).select_from(User)) or 0
    query = await session.scalars(select(User).offset(offset).limit(per_page))
    users = query.all()

    took_ms = int((time.perf_counter() - start_time) * 1000)

    return GenericEnvelope[UserPublic](
        data=users,
        pagination=Pagination.create(
            page=page, per_page=per_page, total_items=total_items
        ),
        filters_applied={"page": page, "per_page": per_page},
        sort=Sort(by="created_at", order="asc"),
        meta=Meta(took_ms=took_ms, cached=False),
        facets=None,
        summary=None,
    )


@router.put("/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: UUID,
    user: UserSchema,
    session: Session,
    current_user: CurrentUser,
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not enough permissions"
        )
    try:
        current_user.username = user.username
        current_user.password = get_password_hash(user.password)
        current_user.email = user.email
        await session.commit()
        await session.refresh(current_user)

        return current_user

    except IntegrityError:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="Username or Email already exists",
        )


@router.delete("/{user_id}", response_model=Message)
async def delete_user(
    user_id: UUID,
    session: Session,
    current_user: CurrentUser,
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not enough permissions"
        )

    await session.delete(current_user)
    await session.commit()

    return {"message": "User deleted"}
