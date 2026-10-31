from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

from simcc_admin.app import app
from simcc_admin.database import get_session
from simcc_admin.models import UserRole, table_registry
from simcc_admin.security import AuthenticatedUser, settings
from tests.factories import (
    CollectionFactory,
    InstitutionFactory,
    ResearcherCollectionFactory,
    ResearcherFactory,
    ResearcherInstitutionFactory,
)


@pytest.fixture(scope="session")
def rsa_key_pair():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


@pytest.fixture(scope="session")
def rsa_private_key(rsa_key_pair):
    return rsa_key_pair[0]


@pytest.fixture(scope="session")
def rsa_public_key_pem(rsa_key_pair):
    return rsa_key_pair[1]


@pytest.fixture(autouse=True)
def setup_idp_public_key(rsa_public_key_pem):
    settings.IDP_PUBLIC_KEY_PEM = rsa_public_key_pem


@pytest.fixture
def client(session):
    def get_session_override():
        return session

    with TestClient(app) as client:
        app.dependency_overrides[get_session] = get_session_override
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def engine():
    with PostgresContainer("postgres:16", driver="psycopg") as postgres:
        _engine = create_async_engine(postgres.get_connection_url())
        yield _engine


@pytest_asyncio.fixture
async def session(engine):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS academic"))
        await conn.run_sync(table_registry.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(table_registry.metadata.drop_all)
        await conn.execute(text("DROP SCHEMA IF EXISTS academic CASCADE"))


@pytest.fixture
def user():
    return AuthenticatedUser(
        id=uuid4(),
        email="user@simcc.org",
        name="Usuário Padrão",
        role=UserRole.DEFAULT,
    )


@pytest.fixture
def other_user():
    return AuthenticatedUser(
        id=uuid4(),
        email="other@simcc.org",
        name="Outro Usuário",
        role=UserRole.DEFAULT,
    )


@pytest.fixture
def admin_user():
    return AuthenticatedUser(
        id=uuid4(),
        email="admin@simcc.org",
        name="Administrador SimCC",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def token_generator(rsa_private_key):
    def _generate(user: AuthenticatedUser) -> str:
        now = datetime.now(UTC)
        payload = {
            "iss": settings.IDP_ISSUER,
            "sub": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role.value,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        }
        return jwt.encode(payload, rsa_private_key, algorithm="RS256")

    return _generate


@pytest.fixture
def token(token_generator, user):
    return token_generator(user)


@pytest.fixture
def admin_token(token_generator, admin_user):
    return token_generator(admin_user)


@pytest.fixture
def admin_client(session, admin_token):
    def get_session_override():
        return session

    with TestClient(
        app, headers={"Authorization": f"Bearer {admin_token}"}
    ) as test_client:
        app.dependency_overrides[get_session] = get_session_override
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def institution_generator(session):
    async def _generate_institution(**kwargs):
        inst = InstitutionFactory(**kwargs)
        session.add(inst)
        await session.commit()
        await session.refresh(inst)
        return inst

    return _generate_institution


@pytest.fixture
def researcher_generator(session):
    async def _generate_researcher(**kwargs):
        res = ResearcherFactory(**kwargs)
        session.add(res)
        await session.commit()
        await session.refresh(res)
        return res

    return _generate_researcher


@pytest.fixture
def researcher_institution_generator(session):
    async def _generate_link(researcher_id, institution_id, **kwargs):
        link = ResearcherInstitutionFactory(
            researcher_id=researcher_id, institution_id=institution_id, **kwargs
        )
        session.add(link)
        await session.commit()
        await session.refresh(link)
        return link

    return _generate_link


@pytest.fixture
def collection_generator(session):
    async def _generate_collection(**kwargs):
        col = CollectionFactory(**kwargs)
        session.add(col)
        await session.commit()
        await session.refresh(col)
        return col

    return _generate_collection


@pytest_asyncio.fixture
async def default_collection(collection_generator):
    return await collection_generator(slug="simcc", name="SimCC", is_default=True)


@pytest.fixture
def researcher_collection_generator(session):
    async def _generate_link(researcher_id, collection_id, **kwargs):
        link = ResearcherCollectionFactory(
            researcher_id=researcher_id, collection_id=collection_id, **kwargs
        )
        session.add(link)
        await session.commit()
        await session.refresh(link)
        return link

    return _generate_link
