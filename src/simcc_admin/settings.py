from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    ADMIN_DATABASE_URL: str = Field(init=False)
    ADMIN_SERVICE_TOKEN: str = Field(default="dev-service-token")

    # Observatório IdP (Central Identity Provider)
    IDP_ISSUER: str = "http://localhost:8000"
    IDP_JWKS_URL: str = "http://localhost:8000/.well-known/jwks.json"
    IDP_AUDIENCE: str | None = None
    IDP_PUBLIC_KEY_PEM: str = ""
