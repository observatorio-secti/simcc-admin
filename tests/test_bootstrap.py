import pytest
from sqlalchemy import func, select

from simcc_admin.bootstrap import bootstrap_academic
from simcc_admin.models import Collection


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
