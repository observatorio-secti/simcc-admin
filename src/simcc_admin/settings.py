from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    DATABASE_URL: str = Field(init=False)
    SECRET_KEY: str = Field(init=False)
    ALGORITHM: str = Field(init=False)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(init=False)

    # Frontend
    FRONTEND_AUTH_CALLBACK_URL: str = "http://localhost:3000/auth/callback"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # ORCID OAuth
    ORCID_CLIENT_ID: str = ""
    ORCID_CLIENT_SECRET: str = ""
    ORCID_REDIRECT_URI: str = "http://localhost:8000/auth/orcid/callback"
    ORCID_SANDBOX: bool = True

    # Administrador Inicial (Bootstrap)
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = "admin@simcc.org"
    ADMIN_PASSWORD: str = "admin123"
