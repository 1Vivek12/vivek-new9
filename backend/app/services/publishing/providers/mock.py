"""Mock publishing providers for automated testing and isolated contract validation.

Explicitly marked with is_mock = True so that simulated execution is never confused
with live external API calls or production state.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.publishing import ConnectedAccount, DestinationType, PlatformPayload
from app.services.publishing.providers.base import (
    ProviderCapabilities,
    ProviderPublishResult,
    PublishingProvider,
)
from app.services.publishing.vault import CredentialVault


class MockPublishingProvider(PublishingProvider):
    """Deterministic mock provider for automated testing across all platform destinations."""

    is_mock = True

    def __init__(
        self,
        destination_type: DestinationType,
        *,
        should_fail: bool = False,
        failure_message: str = "Simulated platform failure",
    ):
        self.destination_type = destination_type
        self.should_fail = should_fail
        self.failure_message = failure_message

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            destination_type=self.destination_type.value,
            max_video_duration_seconds=3600.0,
            supports_resumable_upload=True,
            supported_aspect_ratios=["16:9", "9:16", "1:1", "4:5"],
            supported_media_types=["video/mp4", "image/jpeg", "image/png"],
            max_title_length=100,
            max_body_length=5000,
            supports_scheduling=True,
        )

    async def ensure_valid_credentials(
        self,
        *,
        db: AsyncSession,
        account: ConnectedAccount,
        vault: CredentialVault,
    ) -> Dict[str, Any]:
        return {"access_token": "mock_valid_token_12345", "token_type": "Bearer"}

    async def check_health(
        self,
        *,
        account: ConnectedAccount,
        vault: CredentialVault,
    ) -> bool:
        return not self.should_fail

    async def publish(
        self,
        *,
        db: AsyncSession,
        payload: PlatformPayload,
        account: ConnectedAccount,
        vault: CredentialVault,
        media_assets: List[Dict[str, Any]],
    ) -> ProviderPublishResult:
        if self.should_fail:
            return ProviderPublishResult(
                success=False,
                error_message=self.failure_message,
                raw_response={"mock_error": True, "reason": self.failure_message},
                is_mock=True,
            )

        external_id = f"mock_{self.destination_type.value.lower()}_{uuid.uuid4().hex[:12]}"
        url = f"https://mock.{self.destination_type.value.lower()}.example.com/posts/{external_id}"

        return ProviderPublishResult(
            success=True,
            external_id=external_id,
            url=url,
            raw_response={"mock": True, "external_id": external_id, "url": url},
            is_mock=True,
        )
