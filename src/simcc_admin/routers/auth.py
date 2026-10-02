import secrets
from http import HTTPStatus
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from simcc_admin.database import get_session
from simcc_admin.models import User
from simcc_admin.oauth import (
    authenticate_or_register_oauth_user,
    get_oauth_provider,
)
from simcc_admin.schemas import Token
from simcc_admin.security import (
    create_access_token,
    get_current_user,
    settings,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

OAuth2Form = Annotated[OAuth2PasswordRequestForm, Depends()]
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2Form, session: Session):
    user = await session.scalar(
        select(User).where(
            (User.email == form_data.username) | (User.username == form_data.username)
        )
    )

    if not user or not user.password:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    sub_identifier = user.email or user.username
    access_token = create_access_token(data={"sub": sub_identifier})

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh_token", response_model=Token)
async def refresh_access_token(user: CurrentUser):
    sub_identifier = user.email or user.username
    new_access_token = create_access_token(data={"sub": sub_identifier})

    return {"access_token": new_access_token, "token_type": "bearer"}


@router.get("/{provider}/login")
async def oauth_login(provider: str):
    try:
        oauth_provider = get_oauth_provider(provider, settings)
    except ValueError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=str(e),
        )

    state = secrets.token_urlsafe(32)
    auth_url = oauth_provider.get_authorization_url(state=state)
    return RedirectResponse(url=auth_url, status_code=HTTPStatus.TEMPORARY_REDIRECT)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    session: Session,
    state: str | None = None,
):
    try:
        oauth_provider = get_oauth_provider(provider, settings)
    except ValueError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=str(e),
        )

    try:
        user_info = await oauth_provider.get_user_info(code=code)
    except (httpx.HTTPError, ValueError, KeyError) as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Falha na comunicação com {provider}: {e!s}",
        ) from e

    token = await authenticate_or_register_oauth_user(session, user_info)

    params = urlencode({"token": token.access_token, "token_type": token.token_type})
    separator = "&" if "?" in settings.FRONTEND_AUTH_CALLBACK_URL else "?"
    redirect_target = f"{settings.FRONTEND_AUTH_CALLBACK_URL}{separator}{params}"

    return RedirectResponse(
        url=redirect_target, status_code=HTTPStatus.TEMPORARY_REDIRECT
    )
