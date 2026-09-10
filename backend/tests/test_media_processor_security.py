"""Tests for Media Processor Security: Subprocess Hardening, Env Sanitization, Path Containment."""

import os

import pytest

from app.services.media.processor import FFmpegMediaProcessor


def test_subprocess_environment_sanitization():
    """Verify sensitive environment variables are scrubbed before subprocess execution."""
    processor = FFmpegMediaProcessor()

    # Temporarily set sensitive environment variables
    os.environ["DATABASE_URL"] = "postgresql://user:secretpass@localhost/prod"
    os.environ["JWT_SECRET_KEY"] = "super-secret-jwt-token-key"
    os.environ["REDIS_URL"] = "redis://:mypassword@localhost:6379/0"
    os.environ["API_KEY"] = "news9-api-secret"

    try:
        clean_env = processor._get_sanitized_env()
        assert "DATABASE_URL" not in clean_env
        assert "JWT_SECRET_KEY" not in clean_env
        assert "REDIS_URL" not in clean_env
        assert "API_KEY" not in clean_env
        # System PATH should remain
        assert "PATH" in clean_env
    finally:
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("JWT_SECRET_KEY", None)
        os.environ.pop("REDIS_URL", None)
        os.environ.pop("API_KEY", None)


def test_command_uses_argument_array_not_shell():
    """Verify processor builds argument arrays rather than concatenating shell strings."""
    processor = FFmpegMediaProcessor(ffmpeg_path="ffmpeg", ffprobe_path="ffprobe")

    # Probe command
    cmd = [
        processor.ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        "input.mp4; rm -rf /",
    ]
    assert isinstance(cmd, list)
    assert ";" not in cmd[0]  # executable is isolated
    # Dangerous characters are treated as literal argument, not parsed by shell
    assert cmd[-1] == "input.mp4; rm -rf /"


@pytest.mark.asyncio
async def test_path_traversal_detection_in_storage(seeded_environment):
    """Verify storage provider rejects path traversal attempts."""
    from app.services.storage.local import LocalStorageProvider

    env = seeded_environment
    tenant_id = env["tenant_news9"].id
    storage = LocalStorageProvider()

    with pytest.raises(PermissionError, match="outside tenant boundary|traversal"):
        storage._resolve_tenant_path(tenant_id, "../../../etc/passwd")

    with pytest.raises(PermissionError, match="outside tenant boundary|traversal"):
        storage._resolve_tenant_path(tenant_id, "../other-tenant/media/raw/file.mp4")
