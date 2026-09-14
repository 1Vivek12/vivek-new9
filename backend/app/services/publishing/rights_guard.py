"""Pre-publishing media rights and copyright clearance enforcement.

Reuses and builds upon Phase 5 rights validation primitives to ensure no
unlicensed, restricted, expired, or unverified media asset is ever published.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.services.media.rights import RightsViolationError, validate_rights_for_derivative


class PublishingRightsViolationError(RightsViolationError):
    """Raised when a media asset attached to a publication package violates rights policy."""

    pass


def validate_media_rights_for_publishing(
    media_assets: List[Dict[str, Any]],
) -> bool:
    """Validates rights clearance for all media assets targeted for publishing.

    Rules:
    1. Base derivative rights check must pass (OWNED/LICENSED permitted,
       USER_PROVIDED requires reuse_permitted=True, UNKNOWN/RESTRICTED blocked).
    2. Expiration check: If rights_metadata contains `expires_at`, it must be in the future.
    3. Mandatory metadata check: Rights metadata cannot be null/empty.

    Raises:
        PublishingRightsViolationError: If any asset fails clearance.
    """
    now = datetime.now(timezone.utc)

    for asset in media_assets:
        asset_id = asset.get("asset_id") or asset.get("id", "unknown")
        rights = asset.get("rights_metadata")

        if not rights:
            raise PublishingRightsViolationError(
                f"Publishing blocked: MediaAsset '{asset_id}' has missing or empty rights metadata."
            )

        try:
            validate_rights_for_derivative(rights)
        except RightsViolationError as exc:
            raise PublishingRightsViolationError(
                f"Publishing blocked for MediaAsset '{asset_id}': {str(exc)}"
            ) from exc

        # Expiration check
        expires_at = rights.get("expires_at")
        if expires_at:
            if isinstance(expires_at, str):
                try:
                    exp_dt = datetime.fromisoformat(expires_at)
                except ValueError:
                    exp_dt = None
            elif isinstance(expires_at, datetime):
                exp_dt = expires_at
            else:
                exp_dt = None

            if exp_dt:
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if exp_dt <= now:
                    raise PublishingRightsViolationError(
                        f"Publishing blocked: MediaAsset '{asset_id}' rights expired "
                        f"at {exp_dt.isoformat()}."
                    )

    return True
