import pytest
from sqlalchemy import func, select

from simcc_admin.bootstrap import bootstrap_admin
from simcc_admin.models import User, UserRole


@pytest.mark.asyncio
async def test_bootstrap_admin_creates_admin(session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "superadmin")
    monkeypatch.setenv("ADMIN_EMAIL", "superadmin@simcc.org")
    monkeypatch.setenv("ADMIN_PASSWORD", "supersecret123")

    user = await bootstrap_admin(session=session)
    assert user is not None
    assert user.username == "superadmin"
    assert user.email == "superadmin@simcc.org"
    assert user.role == UserRole.ADMIN

    # Verifica no banco de dados
    db_user = await session.scalar(
        select(User).where(User.email == "superadmin@simcc.org")
    )
    assert db_user is not None
    assert db_user.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_bootstrap_admin_is_idempotent(session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "superadmin")
    monkeypatch.setenv("ADMIN_EMAIL", "superadmin@simcc.org")
    monkeypatch.setenv("ADMIN_PASSWORD", "supersecret123")

    first_call_user = await bootstrap_admin(session=session)
    second_call_user = await bootstrap_admin(session=session)

    assert first_call_user.id == second_call_user.id

    # Verifica que só existe 1 usuário criado
    count = await session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.email == "superadmin@simcc.org")
    )
    assert count == 1


@pytest.mark.asyncio
async def test_bootstrap_admin_missing_env(session, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "")
    result = await bootstrap_admin(session=session)
    assert result is None
