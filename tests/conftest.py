import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

from simcc_admin.app import app
from simcc_admin.database import get_session
from simcc_admin.models import UserRole, table_registry
from simcc_admin.security import get_password_hash
from tests.factories import (
    InstitutionFactory,
    ResearcherFactory,
    ResearcherInstitutionFactory,
    UserFactory,
)


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
def user_generator(session):
    async def _generate_user(**kwargs):
        password = kwargs.pop("password", "testtest")
        user = UserFactory(password=get_password_hash(password), **kwargs)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user.clean_password = password
        return user

    return _generate_user


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
def token_generator(client):
    def _generate_token(user):
        response = client.post(
            "/auth/token",
            data={"username": user.email, "password": user.clean_password},
        )
        return response.json()["access_token"]

    return _generate_token


@pytest_asyncio.fixture
async def user(user_generator):
    return await user_generator()


@pytest_asyncio.fixture
async def other_user(user_generator):
    return await user_generator()


@pytest.fixture
def token(client, user):
    response = client.post(
        "/auth/token",
        data={"username": user.email, "password": user.clean_password},
    )
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def admin_user(user_generator):
    return await user_generator(role=UserRole.ADMIN)


@pytest.fixture
def admin_token(client, admin_user):
    response = client.post(
        "/auth/token",
        data={"username": admin_user.email, "password": admin_user.clean_password},
    )
    return response.json()["access_token"]


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
