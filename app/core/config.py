from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resuelto a partir de la ubicación de este archivo: <repo>/app/core/config.py
# .parents[2] = <repo>. Garantiza que .env se encuentre sin importar el CWD.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "TOOL_API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    TIMEZONE: str = "America/Lima"

    API_V1_PREFIX: str = "/v1"
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    JWT_SECRET: str = Field(...)
    JWT_ALGORITHM: str = "HS256"
    # Static tokens — long-lived by design (default 365 days).
    JWT_ACCESS_TOKEN_EXPIRE_DAYS: int = 365

    SYSTEM_CLIENT_ID: str = "tool-api-client"

    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/tool_api"
    REDIS_URL: str = "redis://localhost:6379/0"

    MS_TENANT_ID: str = ""
    MS_CLIENT_ID: str = ""
    MS_CLIENT_SECRET: str = ""
    MS_GRAPH_SCOPE: str = "https://graph.microsoft.com/.default"

    KISSFLOW_SUBDOMAIN: str = ""
    KISSFLOW_ACCOUNT_ID: str = ""
    KISSFLOW_ACCESS_KEY_ID: str = ""
    KISSFLOW_ACCESS_KEY_SECRET: str = ""

    RATE_LIMIT_DEFAULT: str = "60/minute"

    @field_validator("JWT_SECRET")
    @classmethod
    def _validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        if "change-me" in v:
            raise ValueError("JWT_SECRET must not contain placeholder 'change-me'")
        return v

    @field_validator("JWT_ACCESS_TOKEN_EXPIRE_DAYS")
    @classmethod
    def _validate_expire_days(cls, v: int) -> int:
        if v < 1:
            raise ValueError("JWT_ACCESS_TOKEN_EXPIRE_DAYS must be at least 1")
        return v

    @model_validator(mode="after")
    def _validate_production_debug(self) -> "Settings":
        if self.APP_ENV == "production" and self.DEBUG is True:
            raise ValueError("DEBUG must be False in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
