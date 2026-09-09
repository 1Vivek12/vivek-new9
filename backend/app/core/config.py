"""Configuration module with typed Pydantic v2 settings."""

from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    ENVIRONMENT: str = Field(default="development", description="Current environment")
    DEBUG: bool = Field(default=False, description="Debug mode flag")
    APP_NAME: str = Field(
        default="News 9 AI Content & Newsroom Automation Platform",
        description="Neutral platform branding name",
    )
    APP_VERSION: str = Field(default="1.0.0-phase1")
    API_V1_PREFIX: str = Field(default="/api/v1")
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)

    # CORS
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated allowed origins",
    )

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    # Security & Auth
    SECRET_KEY: str = Field(
        default="CHANGE_THIS_TO_A_SECURE_RANDOM_SECRET_KEY_MIN_32_BYTES",
        description="HMAC secret key for signing tokens",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    ALGORITHM: str = Field(default="HS256")

    # Database (PostgreSQL with asyncpg)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/news9_platform",
        description="Async SQLAlchemy database connection URI",
    )
    DB_POOL_SIZE: int = Field(default=10)
    DB_MAX_OVERFLOW: int = Field(default=20)
    DB_TIMEOUT: int = Field(default=30)

    # Redis & Celery
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1")

    # Storage
    STORAGE_ROOT: str = Field(default="./data/storage")

    # AI Provider (Local inference priority)
    AI_PROVIDER_TYPE: str = Field(default="ollama")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_DEFAULT_MODEL: str = Field(default="llama3")
    OLLAMA_REQUEST_TIMEOUT: int = Field(default=60)

    # Agent Runtime Boundary
    AGENT_RUNTIME_TYPE: str = Field(default="prime_agent")
    AGENT_EXECUTION_ENABLED: bool = Field(
        default=False,
        description="Phase 1: Kept disabled/pending verification for security",
    )
    AGENT_TIMEOUT_SECONDS: int = Field(default=120)

    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(default="json")

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v or not v.startswith(("postgresql+asyncpg://", "sqlite+aiosqlite://")):
            raise ValueError(
                "DATABASE_URL must be a valid async connection string starting with "
                "'postgresql+asyncpg://' (or 'sqlite+aiosqlite://' for local testing)"
            )
        return v


settings = Settings()
