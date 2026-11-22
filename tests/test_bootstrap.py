import pytest
from sqlalchemy import func, select

from simcc_admin.bootstrap import bootstrap_academic, bootstrap_admins
from simcc_admin.models import Admin, Collection


@pytest.mark.asyncio
async def test_bootstrap_academic_creates_simcc_collection(session):
    col = await bootstrap_academic(session=session)
    assert col is not None
    assert col.slug == "simcc"
    assert col.name == "SimCC"
    assert col.is_default is True

    # Verifica no banco de dados
    db_col = await session.scalar(select(Collection).where(Collection.slug == "simcc"))
    assert db_col is not None
    assert db_col.is_default is True


@pytest.mark.asyncio
async def test_bootstrap_academic_is_idempotent(session):
    first_col = await bootstrap_academic(session=session)
    second_col = await bootstrap_academic(session=session)

    assert first_col.id == second_col.id

    count = await session.scalar(
        select(func.count()).select_from(Collection).where(Collection.slug == "simcc")
    )
    assert count == 1


@pytest.mark.asyncio
async def test_bootstrap_admins_creates_and_is_idempotent(session):
    existing = Admin(sub="existing-admin-sub", name="Existing", created_by="manual")
    session.add(existing)
    await session.commit()

    created_first = await bootstrap_admins(
        session=session,
        bootstrap_subs="sub-1, sub-2, sub-1, existing-admin-sub",
    )
    assert [a.sub for a in created_first] == ["sub-1", "sub-2"]

    created_second = await bootstrap_admins(
        session=session,
        bootstrap_subs="sub-1, sub-2",
    )
    assert created_second == []

    all_subs = set(await session.scalars(select(Admin.sub)))
    assert all_subs == {"existing-admin-sub", "sub-1", "sub-2"}
