"""External Media Delivery Service.

Provides secure, time-limited, HMAC-signed public URLs for external platform ingestion
(specifically Instagram Graph API /media ingestion), ensuring multi-tenant path containment,
expiration verification, and media rights clearance.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.core.config import get_settings
from app.services.publishing.rights_guard import (
    validate_media_rights_for_publishing,
)


class DeliverySecurityError(Exception):
    """Raised when delivery token verification or path containment fails."""

    pass


class ExternalMediaDeliveryService:
    """Issues and verifies secure, time-limited download URLs for platform ingestion."""

    DEFAULT_TTL_SECONDS = 900  # 15 minutes as specified in Phase 6 requirements

    def __init__(self, secret_key: Optional[str] = None):
        settings = get_settings()
        self.secret_key = (secret_key or settings.SECRET_KEY).encode("utf-8")
        self.base_url = settings.EXTERNAL_MEDIA_BASE_URL.rstrip("/")

    def generate_delivery_token(
        self,
        *,
        tenant_id: str,
        asset_id: str,
        storage_path: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> str:
        """Generates an HMAC-signed delivery token valid for `ttl_seconds`."""
        expires_at = int(datetime.now(timezone.utc).timestamp()) + ttl_seconds
        payload = {
            "tid": str(tenant_id),
            "aid": str(asset_id),
            "sp": storage_path,
            "exp": expires_at,
        }
        raw_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        sig = hmac.new(self.secret_key, raw_json, hashlib.sha256).hexdigest()
        token_data = {
            "p": base64.urlsafe_b64encode(raw_json).decode("ascii"),
            "s": sig,
        }
        token_bytes = json.dumps(token_data, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(token_bytes).decode("ascii")

    def get_delivery_url(
        self,
        *,
        tenant_id: str,
        asset_id: str,
        storage_path: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> str:
        """Returns the fully qualified delivery URL containing the signed token."""
        token = self.generate_delivery_token(
            tenant_id=tenant_id,
            asset_id=asset_id,
            storage_path=storage_path,
            ttl_seconds=ttl_seconds,
        )
        return f"{self.base_url}/api/v1/publishing/delivery/{token}"

    def verify_and_resolve_file(
        self,
        token: str,
        *,
        asset_rights_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Path, str, str]:
        """Verifies signature, expiration, path containment, and rights.

        Returns:
            Tuple of (Path, tenant_id, asset_id)

        Raises:
            DeliverySecurityError: If token is forged, expired, or attempts path traversal.
            PublishingRightsViolationError: If rights metadata fails clearance.
        """
        try:
            token_json = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
            token_data = json.loads(token_json)
            raw_payload_bytes = base64.urlsafe_b64decode(token_data["p"].encode("ascii"))
            expected_sig = hmac.new(self.secret_key, raw_payload_bytes, hashlib.sha256).hexdigest()
            provided_sig = token_data["s"]

            if not hmac.compare_digest(expected_sig, provided_sig):
                raise DeliverySecurityError("Invalid delivery token signature.")

            payload = json.loads(raw_payload_bytes.decode("utf-8"))
        except Exception as exc:
            if isinstance(exc, DeliverySecurityError):
                raise
            raise DeliverySecurityError(f"Malformed delivery token: {str(exc)}") from exc

        # Check expiration
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if payload.get("exp", 0) < now_ts:
            raise DeliverySecurityError("Delivery token has expired.")

        tenant_id = payload.get("tid")
        asset_id = payload.get("aid")
        storage_path = payload.get("sp")

        if not tenant_id or not asset_id or not storage_path:
            raise DeliverySecurityError("Incomplete delivery token payload.")

        # Path containment enforcement
        settings = get_settings()
        root_dir = getattr(settings, "STORAGE_ROOT", "./storage")
        storage_root = Path(root_dir).resolve()
        resolved_path = (storage_root / storage_path).resolve()

        try:
            # Must be strictly within storage_root
            resolved_path.relative_to(storage_root)
        except ValueError as exc:
            raise DeliverySecurityError(
                "Path traversal attempt detected in delivery path."
            ) from exc

        # Rights check if provided
        if asset_rights_metadata is not None:
            validate_media_rights_for_publishing(
                [{"asset_id": asset_id, "rights_metadata": asset_rights_metadata}]
            )

        if not resolved_path.exists() or not resolved_path.is_file():
            raise DeliverySecurityError("Media file does not exist at requested storage location.")

        return resolved_path, tenant_id, asset_id
