from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class OAuthUserInfo(BaseModel):
    provider: str
    provider_user_id: str
    email: str | None = None
    name: str | None = None
    raw_data: dict = Field(default_factory=dict)


class BaseOAuthProvider(ABC):
    name: str

    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """Gera a URL de consentimento para redirecionar o usuário."""

    @abstractmethod
    async def get_user_info(self, code: str) -> OAuthUserInfo:
        """Troca o authorization code pelo access token e retorna os dados unificados do usuário."""
