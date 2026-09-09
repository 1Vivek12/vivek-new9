"""Configuration validation and failure mode tests."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_valid_configuration_defaults():
    """Verifies that default settings load with valid typed values."""
    settings = Settings()
    assert settings.APP_NAME == "News 9 AI Content & Newsroom Automation Platform"
    assert "asyncpg" in settings.DATABASE_URL
    assert settings.AGENT_EXECUTION_ENABLED is False  # Safe default in Phase 1
    assert len(settings.cors_origins) >= 1


def test_invalid_database_url_raises_validation_error():
    """Verifies that invalid or non-async database URLs are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(DATABASE_URL="mysql://user:pass@localhost/db")
    assert "DATABASE_URL must be a valid async connection string" in str(exc_info.value)


def test_empty_database_url_raises_validation_error():
    """Verifies that empty database URL is rejected."""
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="")
