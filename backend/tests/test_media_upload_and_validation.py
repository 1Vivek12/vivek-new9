"""Tests for Media Upload, Magic Byte MIME Validation, and Storage Security."""

import io

import pytest

from app.services.media.validator import MediaValidationError, validate_media_upload


@pytest.mark.asyncio
async def test_valid_media_upload_and_sha256(client, seeded_environment):
    """Test valid MP4 upload: checks MIME, calculates SHA-256, stores under tenant path."""
    env = seeded_environment
    tenant_id = env["tenant_news9"].id
    headers = {
        "Authorization": f"Bearer {env['token_news9']}",
        "X-Tenant-ID": tenant_id,
    }

    # ISO Base Media File Format signature (ftyp)
    fake_mp4_bytes = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41" + b"\x00" * 200

    files = {
        "file": ("news_report.mp4", io.BytesIO(fake_mp4_bytes), "video/mp4"),
    }
    data = {
        "rights_type": "OWNED",
        "attribution": "News 9 Field Crew",
        "reuse_permitted": "true",
    }

    res = await client.post("/api/v1/media/upload", headers=headers, files=files, data=data)
    assert res.status_code == 201
    payload = res.json()
    assert payload["tenant_id"] == tenant_id
    assert payload["original_filename"] == "news_report.mp4"
    assert payload["mime_type"] == "video/mp4"
    assert payload["media_type"] == "VIDEO"
    assert len(payload["checksum"]) == 64
    assert payload["rights_metadata"]["rights_type"] == "OWNED"
    assert payload["storage_key"].startswith("media/")


@pytest.mark.asyncio
async def test_mime_spoofing_rejected(client, seeded_environment):
    """Test that a file with .mp4 extension but plain text or executable header is rejected."""
    env = seeded_environment
    tenant_id = env["tenant_news9"].id
    headers = {
        "Authorization": f"Bearer {env['token_news9']}",
        "X-Tenant-ID": tenant_id,
    }

    # Fake mp4 containing text script
    malicious_bytes = b"#!/bin/bash\necho 'Hacked'\n"
    files = {
        "file": ("exploit.mp4", io.BytesIO(malicious_bytes), "video/mp4"),
    }
    data = {
        "rights_type": "OWNED",
        "reuse_permitted": "true",
    }

    res = await client.post("/api/v1/media/upload", headers=headers, files=files, data=data)
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert "File header signature does not match" in detail or "spoofing" in detail.lower()


@pytest.mark.asyncio
async def test_disallowed_extension_rejected(client, seeded_environment):
    """Test that non-whitelisted extension is rejected."""
    env = seeded_environment
    tenant_id = env["tenant_news9"].id
    headers = {
        "Authorization": f"Bearer {env['token_news9']}",
        "X-Tenant-ID": tenant_id,
    }

    files = {
        "file": (
            "payload.exe",
            io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00"),
            "application/octet-stream",
        ),
    }
    data = {
        "rights_type": "OWNED",
    }

    res = await client.post("/api/v1/media/upload", headers=headers, files=files, data=data)
    assert res.status_code == 422
    assert "not permitted" in res.json()["detail"].lower()


def test_oversized_file_rejected(monkeypatch):
    """Test validation service rejects files exceeding maximum size."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "MAX_MEDIA_UPLOAD_SIZE_BYTES", 50)
    huge_data = b"\x00\x00\x00\x20ftypisom" + b"0" * 100
    with pytest.raises(MediaValidationError, match="exceeds maximum allowed upload size"):
        validate_media_upload(
            filename="large.mp4",
            content=huge_data,
            declared_mime_type="video/mp4",
        )


@pytest.mark.asyncio
async def test_valid_audio_and_image_upload(client, seeded_environment):
    """Test uploading valid RIFF WAV audio and PNG image."""
    env = seeded_environment
    tenant_id = env["tenant_news9"].id
    headers = {
        "Authorization": f"Bearer {env['token_news9']}",
        "X-Tenant-ID": tenant_id,
    }

    # WAV header: RIFF....WAVEfmt
    wav_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00" + b"\x00" * 50
    res_wav = await client.post(
        "/api/v1/media/upload",
        headers=headers,
        files={"file": ("interview.wav", io.BytesIO(wav_bytes), "audio/wav")},
        data={"rights_type": "OWNED"},
    )
    assert res_wav.status_code == 201
    assert res_wav.json()["media_type"] == "AUDIO"

    # PNG header: \x89PNG\r\n\x1a\n
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
    res_png = await client.post(
        "/api/v1/media/upload",
        headers=headers,
        files={"file": ("photo.png", io.BytesIO(png_bytes), "image/png")},
        data={"rights_type": "LICENSED"},
    )
    assert res_png.status_code == 201
    assert res_png.json()["media_type"] == "IMAGE"
