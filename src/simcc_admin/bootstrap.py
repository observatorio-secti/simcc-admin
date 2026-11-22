import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from simcc_admin.database import engine
from simcc_admin.models import Admin, Collection
from simcc_admin.settings import Settings

logger = logging.getLogger("simcc_admin.bootstrap")


def _parse_subs(raw_subs: str) -> list[str]:
    seen: set[str] = set()
    subs: list[str] = []
    for item in raw_subs.split(","):
        sub = item.strip()
        if sub and sub not in seen:
            seen.add(sub)
            subs.append(sub)
    return subs


async def bootstrap_academic(
    session: AsyncSession | None = None,
) -> Collection | None:
    """Garante que a coleção padrão 'simcc' exista de forma idempotente."""
    should_close = False
    if session is None:
        session = AsyncSession(engine, expire_on_commit=False)
        should_close = True

    try:
        query = select(Collection).where(Collection.slug == "simcc")
        existing_col = await session.scalar(query)
        if existing_col:
            logger.info("Coleção padrão 'simcc' já existente.")
            return existing_col

        col = Collection(
            slug="simcc",
            name="SimCC",
            description="Coleção padrão do SimCC",
            refresh_interval_days=1,
            is_default=True,
        )
        session.add(col)
        await session.commit()
        await session.refresh(col)
        logger.info("Coleção padrão 'simcc' criada com sucesso: %s", col.id)
        return col
    finally:
        if should_close:
            await session.close()


async def bootstrap_admins(
    session: AsyncSession | None = None,
    bootstrap_subs: str | None = None,
) -> list[Admin]:
    """Garante de forma idempotente os admins configurados em ADMIN_BOOTSTRAP_SUBS."""
    subs = (
        _parse_subs(bootstrap_subs)
        if bootstrap_subs is not None
        else Settings().bootstrap_subs_list
    )
    if not subs:
        logger.info("Nenhum sub configurado em ADMIN_BOOTSTRAP_SUBS.")
        return []

    should_close = False
    if session is None:
        session = AsyncSession(engine, expire_on_commit=False)
        should_close = True

    try:
        existing_subs = set(
            await session.scalars(select(Admin.sub).where(Admin.sub.in_(subs)))
        )
        created: list[Admin] = []
        for sub in subs:
            if sub in existing_subs:
                continue
            admin = Admin(sub=sub, created_by="bootstrap")
            session.add(admin)
            created.append(admin)

        if created:
            await session.commit()
            for admin in created:
                await session.refresh(admin)
            logger.info("Admins inseridos no bootstrap: %s", [a.sub for a in created])
        else:
            logger.info("Todos os subs de ADMIN_BOOTSTRAP_SUBS já existem.")
        return created
    finally:
        if should_close:
            await session.close()


async def run_bootstrap() -> None:
    await bootstrap_academic()
    await bootstrap_admins()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Iniciando processo de bootstrap...")
    asyncio.run(run_bootstrap())
    logger.info("Bootstrap concluído.")


if __name__ == "__main__":
    main()
