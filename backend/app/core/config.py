"""Configuration module with typed Pydantic v2 settings."""

from typing import List, Optional

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

    # Phase 5 Media & Video Production
    FFMPEG_BINARY_PATH: str = Field(default="ffmpeg")
    FFPROBE_BINARY_PATH: str = Field(default="ffprobe")
    WHISPER_MODEL_NAME: str = Field(default="base")
    MAX_MEDIA_UPLOAD_SIZE_BYTES: int = Field(default=524_288_000)  # 500 MB
    MAX_MEDIA_DURATION_SECONDS: int = Field(default=7200)  # 2 Hours
    MAX_MEDIA_RESOLUTION_WIDTH: int = Field(default=3840)  # 4K UHD
    MAX_MEDIA_RESOLUTION_HEIGHT: int = Field(default=2160)
    MAX_CONCURRENT_MEDIA_JOBS_PER_TENANT: int = Field(default=3)
    MAX_TEMP_DISK_USAGE_BYTES: int = Field(default=2_147_483_648)  # 2 GB
    MAX_DERIVATIVE_OUTPUT_SIZE_BYTES: int = Field(default=524_288_000)  # 500 MB
    MAX_EXTRACTED_KEYFRAMES: int = Field(default=30)
    MAX_TRANSCRIPT_LENGTH_CHARS: int = Field(default=100_000)
    MAX_OCR_OUTPUT_CHARS: int = Field(default=10_000)
    MAX_DERIVATIVES_PER_MEDIA: int = Field(default=10)
    MEDIA_PROCESSING_TIMEOUT_SECONDS: int = Field(default=180)  # 3 minutes
    # Phase 6 Publishing & Distribution
    PUBLISHING_ENCRYPTION_KEY: Optional[str] = Field(default=None)
    META_GRAPH_API_VERSION: str = Field(default="v21.0")
    META_APP_ID: Optional[str] = Field(default=None)
    META_APP_SECRET: Optional[str] = Field(default=None)
    YOUTUBE_CLIENT_ID: Optional[str] = Field(default=None)
    YOUTUBE_CLIENT_SECRET: Optional[str] = Field(default=None)
    YOUTUBE_WEBHOOK_SECRET: Optional[str] = Field(default=None)
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = Field(default=None)
    WHATSAPP_WABA_ID: Optional[str] = Field(default=None)
    NEWS9_INSTAGRAM_EDITORIAL_MAX_SECONDS: int = Field(default=90)
    NEWS9_YOUTUBE_SHORTS_EDITORIAL_MAX_SECONDS: int = Field(default=180)
    YOUTUBE_TENANT_MAX_UPLOADS_PER_HOUR: int = Field(default=4)  # Application safety limit
    FACEBOOK_MAX_POSTS_PER_HOUR: int = Field(default=10)  # Application safety limit
    INSTAGRAM_MAX_POSTS_PER_HOUR: int = Field(default=10)  # Application safety limit
    WHATSAPP_MESSAGES_PER_SECOND_LIMIT: int = Field(default=20)  # Canonical safety throttle
    WHATSAPP_DAILY_RECIPIENTS_LIMIT: int = Field(default=1000)  # Application safety limit
    EXTERNAL_MEDIA_BASE_URL: str = Field(default="http://localhost:8000")
    META_WEBHOOK_VERIFY_TOKEN: str = Field(default="news9_meta_verify_token")

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


def get_settings() -> Settings:
    """Returns application settings singleton."""
    return settings
