import secrets
from dataclasses import dataclass
from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import (
    DecodeError,
    ExpiredSignatureError,
    InvalidTokenError,
    PyJWKClient,
    decode,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from simcc_admin.database import get_session
from simcc_admin.models import Admin
from simcc_admin.settings import Settings

settings = Settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")
oauth2_optional_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/token", auto_error=False
)

_jwks_client: PyJWKClient | None = None


def get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(
            settings.IDP_JWKS_URL, cache_keys=True, max_cached_keys=16
        )
    return _jwks_client


@dataclass
class AuthenticatedUser:
    """Representação em memória do usuário autenticado via token do IdP e tabela admins."""

    sub: str
    name: str | None
    email: str | None
    is_admin: bool = False


def decode_idp_token(token: str) -> dict:
    """Decodifica e valida assinatura RS256, issuer e audience do token do IdP."""
    if settings.IDP_PUBLIC_KEY_PEM.strip():
        return decode(
            token,
            settings.IDP_PUBLIC_KEY_PEM.strip(),
            algorithms=["RS256"],
            issuer=settings.IDP_ISSUER,
            audience=settings.IDP_AUDIENCE,
            options={"verify_aud": True},
        )

    client = get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)
    return decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=settings.IDP_ISSUER,
        audience=settings.IDP_AUDIENCE,
        options={"verify_aud": True},
    )


async def _is_sub_admin(session: AsyncSession, sub: str) -> bool:
    admin_id = await session.scalar(select(Admin.id).where(Admin.sub == sub))
    return admin_id is not None


async def get_user_from_raw_token(
    token: str,
    session: AsyncSession | None = None,
) -> AuthenticatedUser:
    """Valida o token RS256 e consulta a tabela admins quando uma sessão é fornecida."""
    credentials_exception = HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_idp_token(token)
        subject = payload.get("sub")
        if not subject or not str(subject).strip():
            raise credentials_exception
        sub = str(subject).strip()
    except (DecodeError, ExpiredSignatureError, InvalidTokenError, ValueError):
        raise credentials_exception

    is_admin = await _is_sub_admin(session, sub) if session is not None else False

    return AuthenticatedUser(
        sub=sub,
        name=payload.get("name"),
        email=payload.get("email"),
        is_admin=is_admin,
    )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthenticatedUser:
    return await get_user_from_raw_token(token, session=session)


async def require_admin(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


class RequireServiceTokenOrAdmin:
    """Permite acesso via X-Service-Token ou por usuário presente na tabela admins."""

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
            user = await get_user_from_raw_token(token, session=session)
            if not user.is_admin:
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


AdminUser = Annotated[AuthenticatedUser, Depends(require_admin)]
