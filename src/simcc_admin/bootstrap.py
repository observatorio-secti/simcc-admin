import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from simcc_admin.database import engine
from simcc_admin.models import Collection

logger = logging.getLogger("simcc_admin.bootstrap")


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


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Iniciando processo de bootstrap...")
    asyncio.run(bootstrap_academic())
    logger.info("Bootstrap concluído.")


if __name__ == "__main__":
    main()
