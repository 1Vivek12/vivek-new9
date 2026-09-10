"""Media validation and signature inspection service."""

import hashlib
import os
import uuid
from typing import Dict, List, Optional, Set, Tuple

from app.core.config import settings

# Recognized magic bytes signatures
FILE_SIGNATURES: Dict[str, List[bytes]] = {
    "video/mp4": [
        b"\x00\x00\x00\x18ftyp",
        b"\x00\x00\x00\x20ftyp",
        b"\x00\x00\x00\x1cftyp",
        b"ftyp",
    ],
    "video/quicktime": [b"moov", b"mdat", b"ftypqt"],
    "video/webm": [b"\x1a\x45\xdf\xa3"],
    "video/x-matroska": [b"\x1a\x45\xdf\xa3"],
    "audio/mpeg": [b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"],
    "audio/wav": [b"RIFF"],
    "audio/x-wav": [b"RIFF"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],
}

ALLOWED_EXTENSIONS: Set[str] = {
    ".mp4",
    ".mov",
    ".webm",
    ".mkv",
    ".mp3",
    ".wav",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

EXTENSION_TO_MEDIA_TYPE: Dict[str, str] = {
    ".mp4": "VIDEO",
    ".mov": "VIDEO",
    ".webm": "VIDEO",
    ".mkv": "VIDEO",
    ".mp3": "AUDIO",
    ".wav": "AUDIO",
    ".jpg": "IMAGE",
    ".jpeg": "IMAGE",
    ".png": "IMAGE",
    ".webp": "IMAGE",
}

EXTENSION_TO_MIME: Dict[str, str] = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class MediaValidationError(ValueError):
    """Raised when uploaded media fails safety, format, or size validation."""

    pass


def sanitize_filename(filename: str) -> str:
    """Strip path traversal elements and unsafe characters from original filename."""
    base = os.path.basename(filename)
    safe_chars = [c for c in base if c.isalnum() or c in ("-", "_", ".")]
    cleaned = "".join(safe_chars).strip()
    return cleaned[:255] if cleaned else "media_file"


def validate_media_upload(
    filename: str,
    content: bytes,
    declared_mime_type: Optional[str] = None,
) -> Tuple[str, str, str, str]:
    """Validates raw media upload integrity, MIME signature, size, and generates safe filename.

    Returns:
        Tuple of (safe_storage_filename, media_type, verified_mime, sha256_checksum)
    """
    if not content:
        raise MediaValidationError("Uploaded media file is empty (0 bytes).")

    size_bytes = len(content)
    if size_bytes > settings.MAX_MEDIA_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_MEDIA_UPLOAD_SIZE_BYTES // (1024 * 1024)
        current_mb = size_bytes // (1024 * 1024)
        raise MediaValidationError(
            f"File size ({current_mb} MB) exceeds maximum allowed upload size of {max_mb} MB."
        )

    # 1. Extension validation
    clean_name = sanitize_filename(filename)
    _, ext = os.path.splitext(clean_name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise MediaValidationError(
            f"File extension '{ext}' is not permitted. Allowed: {allowed_list}"
        )

    media_type = EXTENSION_TO_MEDIA_TYPE[ext]
    expected_mime = EXTENSION_TO_MIME[ext]

    # 2. Magic byte signature inspection
    header_sample = content[:64]
    matched_signature = False

    # Check against known signatures
    signatures = FILE_SIGNATURES.get(expected_mime, [])
    for sig in signatures:
        if sig in header_sample:
            matched_signature = True
            break

    # If MIME doesn't match expected signatures, reject spoofed file
    if signatures and not matched_signature:
        raise MediaValidationError(
            f"File header signature does not match declared format for extension '{ext}'."
        )

    verified_mime = (
        declared_mime_type
        if declared_mime_type and declared_mime_type == expected_mime
        else expected_mime
    )

    # 3. Checksum calculation
    sha256 = hashlib.sha256(content).hexdigest()

    # 4. Generate unique, non-user-controlled storage filename
    unique_name = f"{uuid.uuid4().hex}{ext}"

    return unique_name, media_type, verified_mime, sha256
