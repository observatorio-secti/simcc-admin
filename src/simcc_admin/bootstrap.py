import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from simcc_admin.database import engine
from simcc_admin.models import User, UserRole
from simcc_admin.security import get_password_hash
from simcc_admin.settings import Settings

logger = logging.getLogger("simcc_admin.bootstrap")


async def bootstrap_admin(
    session: AsyncSession | None = None,
    settings: Settings | None = None,
) -> User | None:
    """Cria o usuário administrador inicial de forma idempotente.

    Se uma sessão não for fornecida, utiliza o engine da aplicação.
    """
    if settings is None:
        settings = Settings()

    if not settings.ADMIN_EMAIL or not settings.ADMIN_USERNAME:
        logger.warning(
            "ADMIN_EMAIL ou ADMIN_USERNAME não configurados. Pulando bootstrap."
        )
        return None

    should_close = False
    if session is None:
        session = AsyncSession(engine, expire_on_commit=False)
        should_close = True

    try:
        query = select(User).where(
            (User.email == settings.ADMIN_EMAIL)
            | (User.username == settings.ADMIN_USERNAME)
        )
        existing_user = await session.scalar(query)

        if existing_user:
            logger.info(
                "Administrador já existente no sistema: %s (%s). Pulando criação.",
                existing_user.username,
                existing_user.email,
            )
            return existing_user

        admin_user = User(
            username=settings.ADMIN_USERNAME,
            email=settings.ADMIN_EMAIL,
            password=get_password_hash(settings.ADMIN_PASSWORD),
            role=UserRole.ADMIN,
        )
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)
        logger.info(
            "Administrador inicial criado com sucesso: %s (%s) [ID: %s]",
            admin_user.username,
            admin_user.email,
            admin_user.id,
        )
        return admin_user
    finally:
        if should_close:
            await session.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Iniciando processo de bootstrap...")
    asyncio.run(bootstrap_admin())
    logger.info("Bootstrap concluído.")


if __name__ == "__main__":
    main()
