from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    ADMIN_DATABASE_URL: str = Field(init=False)
    ADMIN_SERVICE_TOKEN: str = Field(default="dev-service-token")

    # Prefixo de rota para deployments atrás de proxy reverso (ex: /simcc/admin)
    ROOT_PATH: str = Field(
        default="",
        validation_alias=AliasChoices(
            "ROOT_PATH", "ADMIN_ROOT_PATH", "API_ROOT_PATH", "FASTAPI_ROOT_PATH"
        ),
    )

    # Observatório IdP (Central Identity Provider)
    IDP_ISSUER: str = "http://localhost:8000"
    IDP_JWKS_URL: str = "http://localhost:8000/.well-known/jwks.json"
    IDP_AUDIENCE: str = Field(min_length=1)
    IDP_PUBLIC_KEY_PEM: str = ""

    # Bootstrap inicial de administradores (lista de subs separados por vírgula)
    ADMIN_BOOTSTRAP_SUBS: str = ""

    # Integração servidor-servidor com simcc-etl
    ETL_API_URL: str = ""
    ETL_API_KEY: str = ""

    # Origens permitidas no CORS (separadas por vírgula)
    CORS_ORIGINS: str = "http://localhost:8080"

    @field_validator("ROOT_PATH", mode="before")
    @classmethod
    def assemble_root_path(cls, v: str | None) -> str:
        if not v:
            return ""
        v = v.strip().strip("/")
        return f"/{v}" if v else ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def bootstrap_subs_list(self) -> list[str]:
        seen: set[str] = set()
        subs: list[str] = []
        for item in self.ADMIN_BOOTSTRAP_SUBS.split(","):
            sub = item.strip()
            if sub and sub not in seen:
                seen.add(sub)
                subs.append(sub)
        return subs
