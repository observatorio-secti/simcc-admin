from http import HTTPStatus
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from httpx import Request, Response
from sqlalchemy import select

from simcc_admin.models import OAuthAccount, User
from simcc_admin.oauth.base import OAuthUserInfo
from simcc_admin.oauth.google import GoogleOAuthProvider
from simcc_admin.oauth.orcid import OrcidOAuthProvider
from simcc_admin.oauth.registry import get_oauth_provider
from simcc_admin.oauth.service import authenticate_or_register_oauth_user
from simcc_admin.settings import Settings


def test_registry_providers():
    settings = Settings()
    google = get_oauth_provider("google", settings)
    assert isinstance(google, GoogleOAuthProvider)
    assert google.name == "google"

    orcid = get_oauth_provider("orcid", settings)
    assert isinstance(orcid, OrcidOAuthProvider)
    assert orcid.name == "orcid"

    with pytest.raises(ValueError, match="não suportado"):
        get_oauth_provider("facebook", settings)


def test_google_authorization_url():
    settings = Settings()
    settings.GOOGLE_CLIENT_ID = "test-google-id"
    settings.GOOGLE_REDIRECT_URI = "http://localhost:8000/auth/google/callback"

    provider = GoogleOAuthProvider(settings)
    auth_url = provider.get_authorization_url(state="secure_state")

    parsed = urlparse(auth_url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "accounts.google.com"
    params = parse_qs(parsed.query)
    assert params["client_id"] == ["test-google-id"]
    assert params["redirect_uri"] == ["http://localhost:8000/auth/google/callback"]
    assert params["state"] == ["secure_state"]
    assert params["response_type"] == ["code"]


@pytest.mark.asyncio
async def test_google_get_user_info():
    settings = Settings()
    provider = GoogleOAuthProvider(settings)

    mock_token_resp = Response(
        status_code=200,
        json={"access_token": "google_access_token_123"},
        request=Request("POST", "https://oauth2.googleapis.com/token"),
    )
    mock_userinfo_resp = Response(
        status_code=200,
        json={
            "sub": "google-user-sub-123",
            "email": "user@gmail.com",
            "name": "Google User",
        },
        request=Request("GET", "https://www.googleapis.com/oauth2/v3/userinfo"),
    )

    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get,
    ):
        mock_post.return_value = mock_token_resp
        mock_get.return_value = mock_userinfo_resp

        user_info = await provider.get_user_info(code="sample_code")

        assert user_info.provider == "google"
        assert user_info.provider_user_id == "google-user-sub-123"
        assert user_info.email == "user@gmail.com"
        assert user_info.name == "Google User"


def test_orcid_authorization_url():
    settings = Settings()
    settings.ORCID_CLIENT_ID = "test-orcid-id"
    settings.ORCID_SANDBOX = True

    provider = OrcidOAuthProvider(settings)
    auth_url = provider.get_authorization_url(state="orcid_state")

    parsed = urlparse(auth_url)
    assert parsed.netloc == "sandbox.orcid.org"
    params = parse_qs(parsed.query)
    assert params["client_id"] == ["test-orcid-id"]
    assert params["state"] == ["orcid_state"]
    assert params["scope"] == ["/authenticate"]


@pytest.mark.asyncio
async def test_orcid_get_user_info():
    settings = Settings()
    provider = OrcidOAuthProvider(settings)

    mock_token_resp = Response(
        status_code=200,
        json={
            "access_token": "orcid_token_123",
            "orcid": "0000-0002-1825-0097",
            "name": "Jane Researcher",
        },
        request=Request("POST", "https://sandbox.orcid.org/oauth/token"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_token_resp

        user_info = await provider.get_user_info(code="orcid_code")

        assert user_info.provider == "orcid"
        assert user_info.provider_user_id == "0000-0002-1825-0097"
        assert user_info.name == "Jane Researcher"
        assert user_info.email is None


@pytest.mark.asyncio
async def test_authenticate_or_register_new_user(session):
    user_info = OAuthUserInfo(
        provider="google",
        provider_user_id="google-sub-456",
        email="newuser@example.com",
        name="New User",
    )

    token = await authenticate_or_register_oauth_user(session, user_info)
    assert token.access_token is not None

    db_user = await session.scalar(
        select(User).where(User.email == "newuser@example.com")
    )
    assert db_user is not None
    assert db_user.password is None

    account = await session.scalar(
        select(OAuthAccount).where(OAuthAccount.provider_user_id == "google-sub-456")
    )
    assert account is not None
    assert account.user_id == db_user.id


@pytest.mark.asyncio
async def test_authenticate_or_register_existing_email_links_account(session, user):
    user_info = OAuthUserInfo(
        provider="google",
        provider_user_id="google-sub-existing",
        email=user.email,
        name="Linked User",
    )

    token = await authenticate_or_register_oauth_user(session, user_info)
    assert token.access_token is not None

    # Verifica se a conta OAuth foi associada ao user existente
    account = await session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider_user_id == "google-sub-existing"
        )
    )
    assert account is not None
    assert account.user_id == user.id


@pytest.mark.asyncio
async def test_authenticate_or_register_orcid_without_email(session):
    user_info = OAuthUserInfo(
        provider="orcid",
        provider_user_id="0000-0001-2345-6789",
        email=None,
        name="Professor X",
    )

    token = await authenticate_or_register_oauth_user(session, user_info)
    assert token.access_token is not None

    account = await session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider_user_id == "0000-0001-2345-6789"
        )
    )
    assert account is not None

    user = await session.scalar(select(User).where(User.id == account.user_id))
    assert user is not None
    assert user.email is None
    assert "professor" in user.username

    # Autenticar novamente com a mesma conta não deve criar novo usuário
    token2 = await authenticate_or_register_oauth_user(session, user_info)
    assert token2.access_token is not None

    accounts = (
        await session.scalars(
            select(OAuthAccount).where(
                OAuthAccount.provider_user_id == "0000-0001-2345-6789"
            )
        )
    ).all()
    assert len(accounts) == 1


def test_oauth_login_redirect(client):
    response = client.get("/auth/google/login", follow_redirects=False)
    assert response.status_code == HTTPStatus.TEMPORARY_REDIRECT
    assert "accounts.google.com" in response.headers["location"]


def test_oauth_login_unknown_provider(client):
    response = client.get("/auth/unknown_prov/login")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_oauth_callback_success_redirect_to_frontend(client):
    mock_user_info = OAuthUserInfo(
        provider="google",
        provider_user_id="sub-test-callback-1",
        email="callback_user@example.com",
        name="Callback User",
    )

    with patch(
        "simcc_admin.oauth.google.GoogleOAuthProvider.get_user_info",
        new_callable=AsyncMock,
    ) as mock_get_info:
        mock_get_info.return_value = mock_user_info

        response = client.get(
            "/auth/google/callback?code=mock_code&state=mock_state",
            follow_redirects=False,
        )

        assert response.status_code == HTTPStatus.TEMPORARY_REDIRECT
        location = response.headers["location"]
        assert "http://localhost:3000/auth/callback" in location
        assert "token=" in location
        assert "token_type=bearer" in location

        # Extrai token para testar autenticação na API
        parsed = urlparse(location)
        token_val = parse_qs(parsed.query)["token"][0]

        # Faz requisição autenticada com o token recebido
        users_resp = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token_val}"},
        )
        assert users_resp.status_code == HTTPStatus.OK
        assert users_resp.json()["email"] == "callback_user@example.com"


def test_oauth_callback_provider_error(client):
    with patch(
        "simcc_admin.oauth.google.GoogleOAuthProvider.get_user_info",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectTimeout("Timeout no provedor"),
    ):
        response = client.get(
            "/auth/google/callback?code=bad_code",
            follow_redirects=False,
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert "Timeout no provedor" in response.json()["detail"]


def test_oauth_user_cannot_login_with_password(client):
    # Cria usuário via callback OAuth
    mock_user_info = OAuthUserInfo(
        provider="google",
        provider_user_id="sub-oauth-pwd-test",
        email="oauth_pwd@example.com",
    )
    with patch(
        "simcc_admin.oauth.google.GoogleOAuthProvider.get_user_info",
        new_callable=AsyncMock,
        return_value=mock_user_info,
    ):
        client.get("/auth/google/callback?code=mock_code", follow_redirects=False)

    # Tenta logar via /auth/token com senha aleatória
    response = client.post(
        "/auth/token",
        data={"username": "oauth_pwd@example.com", "password": "anypassword"},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect email or password"
