"""Settings tipados de CAPI-KISABELLA.

Validación estricta al startup: si falta una variable required o tiene
formato inválido, el proceso falla rápido con ValidationError.

Convenciones:
- Secrets se modelan como SecretStr para evitar logging accidental.
- DATABASE_URL solo acepta schemes postgresql.
- LOG_LEVEL es un Literal cerrado (Python logging levels estándar).
- SECRET_KEY debe tener al menos 32 caracteres.

Uso desde FastAPI:
    from core.config import get_settings
    settings = get_settings()  # cacheado vía lru_cache

Uso desde tests:
    Settings(_env_file=None, anthropic_api_key="test", ...)
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM (ADR-007: langchain-anthropic) ---
    anthropic_api_key: SecretStr
    anthropic_model: str = "claude-sonnet-4-6"

    # --- Servicios externos ---
    tavily_api_key: SecretStr = Field(default=SecretStr(""))
    banxico_token: SecretStr = Field(default=SecretStr(""))
    banxico_url: str = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/SF43718/datos/oportuno"

    # --- Base de datos ---
    database_url: str
    # Rol dueño (DDL) para Alembic. Si falta, se usa database_url.
    migration_database_url: str | None = None

    # --- Seguridad ---
    secret_key: SecretStr
    allowed_ips: str = "127.0.0.1"

    # --- Contexto RLS (ADR-008) ---
    app_user_id: str = "00000000-0000-0000-0000-000000000001"

    # --- Frontend / red interna Docker ---
    api_url_internal: str = "http://backend:8000"
    next_public_api_url: str = "http://localhost:8000"
    # Origen del navegador permitido por CORS (el frontend, no la API).
    frontend_origin: str = "http://localhost:3000"

    # --- Observabilidad ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # --- Chat + uploads (Sprint 5) ---
    upload_root: str = "/data/uploads"
    max_file_size_bytes: int = 5 * 1024 * 1024
    max_files_per_message: int = 3
    max_messages_per_conversation: int = 60
    chat_max_input_tokens: int = 60_000
    chat_max_output_tokens: int = 2_000
    chat_temperature: float = 0.4
    chat_history_soft_warn_at: int = 24
    markitdown_timeout_s: int = 20

    @field_validator("secret_key")
    @classmethod
    def _secret_key_min_length(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 32:
            raise ValueError(
                "SECRET_KEY debe tener al menos 32 caracteres "
                "(generar con: python -c 'import secrets; print(secrets.token_urlsafe(32))')"
            )
        return v

    @field_validator("database_url")
    @classmethod
    def _database_url_scheme(cls, v: str) -> str:
        valid_schemes = (
            "postgresql://",
            "postgresql+psycopg://",
            "postgresql+asyncpg://",
        )
        if not v.startswith(valid_schemes):
            raise ValueError(
                f"DATABASE_URL debe usar uno de estos schemes: {', '.join(valid_schemes)}"
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    @property
    def migrations_url(self) -> str:
        return self.migration_database_url or self.database_url


    """Singleton de Settings cacheado.

    Lazy: la primera llamada lee `.env` y valida. Si falta alguna var
    required o el formato es inválido, lanza ValidationError aquí (no en import).
    """
    return Settings()
