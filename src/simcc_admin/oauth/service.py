from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from simcc_admin.models import OAuthAccount, User
from simcc_admin.oauth.base import OAuthUserInfo
from simcc_admin.schemas import Token
from simcc_admin.security import create_access_token


async def _generate_unique_username(session: AsyncSession, base: str) -> str:
    cleaned = "".join(c for c in base if c.isalnum() or c in ("_", "-")).lower()
    if not cleaned:
        cleaned = "user"
    candidate = cleaned
    counter = 1
    while await session.scalar(select(User).where(User.username == candidate)):
        candidate = f"{cleaned}_{counter}"
        counter += 1
    return candidate


async def authenticate_or_register_oauth_user(
    session: AsyncSession, user_info: OAuthUserInfo
) -> Token:
    # 1. Procura se a conta OAuth já está vinculada a algum usuário
    query = (
        select(User)
        .join(OAuthAccount)
        .where(
            OAuthAccount.provider == user_info.provider,
            OAuthAccount.provider_user_id == user_info.provider_user_id,
        )
    )
    user = await session.scalar(query)

    # 2. Se não encontrou pela conta OAuth, verifica se existe usuário com o mesmo e-mail
    if not user and user_info.email:
        user = await session.scalar(select(User).where(User.email == user_info.email))
        if user:
            # Vincula a conta OAuth ao usuário existente
            account = OAuthAccount(
                user_id=user.id,
                provider=user_info.provider,
                provider_user_id=user_info.provider_user_id,
            )
            session.add(account)
            await session.commit()

    # 3. Se o usuário ainda não existe, cria um novo
    if not user:
        if user_info.email:
            base_name = user_info.email.split("@")[0]
        elif user_info.name:
            base_name = user_info.name
        else:
            base_name = f"{user_info.provider}_{user_info.provider_user_id}"

        username = await _generate_unique_username(session, base_name)

        user = User(
            username=username,
            email=user_info.email,
            password=None,
        )
        session.add(user)
        await session.flush()

        account = OAuthAccount(
            user_id=user.id,
            provider=user_info.provider,
            provider_user_id=user_info.provider_user_id,
        )
        session.add(account)
        await session.commit()
        await session.refresh(user)

    # 4. Emite o JWT padrão da aplicação
    sub_identifier = user.email or user.username
    access_token = create_access_token(data={"sub": sub_identifier})
    return Token(access_token=access_token, token_type="bearer")
