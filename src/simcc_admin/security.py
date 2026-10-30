import secrets
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import DecodeError, ExpiredSignatureError, decode, encode
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from simcc_admin.database import get_session
from simcc_admin.models import User, UserRole
from simcc_admin.settings import Settings

settings = Settings()
pwd_context = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", refreshUrl="auth/refresh")
oauth2_optional_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/token", refreshUrl="auth/refresh", auto_error=False
)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(tz=ZoneInfo("UTC")) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    encoded_jwt = encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def get_password_hash(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


async def get_user_from_raw_token(session: AsyncSession, token: str) -> User:
    credentials_exception = HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        subject = payload.get("sub")

        if not subject:
            raise credentials_exception

    except DecodeError:
        raise credentials_exception

    except ExpiredSignatureError:
        raise credentials_exception

    user = await session.scalar(
        select(User).where((User.email == subject) | (User.username == subject))
    )

    if not user:
        raise credentials_exception

    return user


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    token: Annotated[str, Depends(oauth2_scheme)],
):
    return await get_user_from_raw_token(session, token)


# Hierarquia extensível de permissões de cargos
ROLE_HIERARCHY: dict[UserRole, set[UserRole]] = {
    UserRole.ADMIN: {UserRole.ADMIN, UserRole.DEFAULT},
    UserRole.DEFAULT: {UserRole.DEFAULT},
}


class RequireRole:
    """Dependência genérica reutilizável para proteção de endpoints por cargos."""

    def __init__(self, *allowed_roles: UserRole, check_hierarchy: bool = True):
        self.allowed_roles = set(allowed_roles)
        self.check_hierarchy = check_hierarchy

    async def __call__(
        self, current_user: Annotated[User, Depends(get_current_user)]
    ) -> User:
        effective_roles = (
            ROLE_HIERARCHY.get(current_user.role, {current_user.role})
            if self.check_hierarchy
            else {current_user.role}
        )
        if not self.allowed_roles.intersection(effective_roles):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user


class RequireServiceTokenOrRole:
    """Permite acesso via X-Service-Token ou por usuário com cargo permitido."""

    def __init__(self, *allowed_roles: UserRole, check_hierarchy: bool = True):
        self.allowed_roles = set(allowed_roles)
        self.check_hierarchy = check_hierarchy

    async def __call__(
        self,
        session: Annotated[AsyncSession, Depends(get_session)],
        x_service_token: Annotated[str | None, Header()] = None,
        token: Annotated[str | None, Depends(oauth2_optional_scheme)] = None,
    ) -> bool:
        if x_service_token is not None:
            if secrets.compare_digest(x_service_token, settings.ADMIN_SERVICE_TOKEN):
                return True
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail="Invalid service token",
            )

        if token:
            user = await get_user_from_raw_token(session, token)
            effective_roles = (
                ROLE_HIERARCHY.get(user.role, {user.role})
                if self.check_hierarchy
                else {user.role}
            )
            if not self.allowed_roles.intersection(effective_roles):
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail="Not enough permissions",
                )
            return True

        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )


AdminUser = Annotated[User, Depends(RequireRole(UserRole.ADMIN))]
