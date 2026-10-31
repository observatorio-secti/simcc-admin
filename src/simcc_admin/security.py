import secrets
from dataclasses import dataclass
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import (
    DecodeError,
    ExpiredSignatureError,
    InvalidTokenError,
    PyJWKClient,
    decode,
)

from simcc_admin.models import UserRole
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
    """Representação em memória do usuário autenticado validado via token do IdP."""

    id: UUID
    email: str | None
    name: str | None
    role: UserRole


def decode_idp_token(token: str) -> dict:
    """Decodifica e valida a assinatura RS256 do token emitido pelo Observatório IdP."""
    if settings.IDP_PUBLIC_KEY_PEM.strip():
        return decode(
            token,
            settings.IDP_PUBLIC_KEY_PEM.strip(),
            algorithms=["RS256"],
            issuer=settings.IDP_ISSUER,
            options={"verify_aud": bool(settings.IDP_AUDIENCE)},
            audience=settings.IDP_AUDIENCE,
        )

    client = get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)
    return decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=settings.IDP_ISSUER,
        options={"verify_aud": bool(settings.IDP_AUDIENCE)},
        audience=settings.IDP_AUDIENCE,
    )


async def get_user_from_raw_token(token: str) -> AuthenticatedUser:
    """Extrai e valida os dados de identidade diretamente do token RS256 de forma stateless."""
    credentials_exception = HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_idp_token(token)
        subject = payload.get("sub")
        if not subject:
            raise credentials_exception
        user_id = UUID(str(subject))
    except (DecodeError, ExpiredSignatureError, InvalidTokenError, ValueError):
        raise credentials_exception

    email = payload.get("email")
    name = payload.get("name")
    raw_role = payload.get("role", "DEFAULT")
    role = UserRole.ADMIN if str(raw_role).upper() == "ADMIN" else UserRole.DEFAULT

    return AuthenticatedUser(
        id=user_id,
        email=email,
        name=name,
        role=role,
    )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> AuthenticatedUser:
    return await get_user_from_raw_token(token)


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
        self, current_user: Annotated[AuthenticatedUser, Depends(get_current_user)]
    ) -> AuthenticatedUser:
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
            user = await get_user_from_raw_token(token)
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


AdminUser = Annotated[AuthenticatedUser, Depends(RequireRole(UserRole.ADMIN))]
