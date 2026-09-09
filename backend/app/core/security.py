"""Security and cryptographic operations without unnecessary heavy C dependencies."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict, Optional

from app.core.config import settings


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a unique salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}:{key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the stored salt:hash."""
    try:
        salt, key_hex = hashed_password.split(":")
        expected_key = hashlib.pbkdf2_hmac(
            "sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100_000
        )
        return hmac.compare_digest(expected_key.hex(), key_hex)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta_seconds: Optional[int] = None) -> str:
    """Generate a standard HS256-signed JWT token using standard library HMAC."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = data.copy()
    exp = time.time() + (
        expires_delta_seconds
        if expires_delta_seconds is not None
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    payload["exp"] = int(exp)
    payload["iat"] = int(time.time())

    def b64_url_encode(raw_bytes: bytes) -> str:
        return base64.urlsafe_b64encode(raw_bytes).decode("utf-8").rstrip("=")

    header_b64 = b64_url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = b64_url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}"

    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_b64 = b64_url_encode(signature)

    return f"{signing_input}.{sig_b64}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify HS256 signature and return decoded payload if valid and unexpired."""
    parts = token.split(".")
    if len(parts) != 3:
        return None

    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}"

    def b64_url_decode(s: str) -> bytes:
        padded = s + "=" * (-len(s) % 4)
        return base64.urlsafe_b64decode(padded)

    try:
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        provided_sig = b64_url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None

        payload_bytes = b64_url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        if payload.get("exp") and time.time() > payload["exp"]:
            return None

        return payload
    except Exception:
        return None
