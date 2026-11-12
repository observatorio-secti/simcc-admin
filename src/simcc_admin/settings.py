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
    IDP_AUDIENCE: str | None = None
    IDP_PUBLIC_KEY_PEM: str = ""

    @field_validator("ROOT_PATH", mode="before")
    @classmethod
    def assemble_root_path(cls, v: str | None) -> str:
        if not v:
            return ""
        v = v.strip().strip("/")
        return f"/{v}" if v else ""
