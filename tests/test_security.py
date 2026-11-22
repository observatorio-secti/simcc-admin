from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException

from simcc_admin.security import (
    AuthenticatedUser,
    get_user_from_raw_token,
    settings,
)


@pytest.mark.asyncio
async def test_get_user_from_raw_token_valid(rsa_private_key, rsa_public_key_pem):
    settings.IDP_PUBLIC_KEY_PEM = rsa_public_key_pem
    sub = str(uuid4())
    now = datetime.now(UTC)
    payload = {
        "iss": settings.IDP_ISSUER,
        "aud": settings.IDP_AUDIENCE,
        "sub": sub,
        "email": "pesquisador@secti.ba.gov.br",
        "name": "Pesquisador Teste",
        "role": "ADMIN",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(payload, rsa_private_key, algorithm="RS256")

    user = await get_user_from_raw_token(token)
    assert isinstance(user, AuthenticatedUser)
    assert user.sub == sub
    assert user.email == "pesquisador@secti.ba.gov.br"
    assert user.name == "Pesquisador Teste"
    # role no token do IdP não concede admin sem consulta à tabela admins
    assert user.is_admin is False


@pytest.mark.asyncio
async def test_get_user_from_raw_token_invalid_audience(
    rsa_private_key, rsa_public_key_pem
):
    settings.IDP_PUBLIC_KEY_PEM = rsa_public_key_pem
    now = datetime.now(UTC)
    payload = {
        "iss": settings.IDP_ISSUER,
        "aud": "observatorio",
        "sub": str(uuid4()),
        "email": "outro@secti.ba.gov.br",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(payload, rsa_private_key, algorithm="RS256")

    with pytest.raises(HTTPException) as exc_info:
        await get_user_from_raw_token(token)
    assert exc_info.value.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_user_from_raw_token_invalid_signature(rsa_public_key_pem):
    settings.IDP_PUBLIC_KEY_PEM = rsa_public_key_pem
    with pytest.raises(HTTPException) as exc_info:
        await get_user_from_raw_token("invalid-or-malformed-token")
    assert exc_info.value.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_user_from_raw_token_expired(rsa_private_key, rsa_public_key_pem):
    settings.IDP_PUBLIC_KEY_PEM = rsa_public_key_pem
    now = datetime.now(UTC) - timedelta(hours=2)
    payload = {
        "iss": settings.IDP_ISSUER,
        "aud": settings.IDP_AUDIENCE,
        "sub": str(uuid4()),
        "email": "expired@simcc.org",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    token = jwt.encode(payload, rsa_private_key, algorithm="RS256")

    with pytest.raises(HTTPException) as exc_info:
        await get_user_from_raw_token(token)
    assert exc_info.value.status_code == HTTPStatus.UNAUTHORIZED
