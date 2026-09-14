"""News 9 Website internal publishing provider.

Handles direct publishing to the News 9 web content management system, transitioning
Phase 2 Story records to EditorialState.PUBLISHED, generating SEO canonical URLs,
and recording published items.
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models.publishing import (
    ConnectedAccount,
    DestinationType,
    PlatformPayload,
    PublishingPackage,
)
from app.db.models.story import Story
from app.services.editorial.lifecycle import EditorialState
from app.services.publishing.providers.base import (
    ProviderCapabilities,
    ProviderPublishResult,
    PublishingProvider,
)
from app.services.publishing.vault import CredentialVault


class WebsitePublishingProvider(PublishingProvider):
    """Internal provider for News 9 website publishing."""

    destination_type = DestinationType.WEBSITE
    is_mock = False

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            destination_type=DestinationType.WEBSITE.value,
            max_video_duration_seconds=86400.0,
            supports_resumable_upload=False,
            supported_aspect_ratios=["16:9", "1:1", "9:16", "4:5"],
            supported_media_types=["image/jpeg", "image/png", "video/mp4"],
            max_title_length=300,
            max_body_length=500000,
            supports_scheduling=True,
        )

    async def ensure_valid_credentials(
        self,
        *,
        db: AsyncSession,
        account: ConnectedAccount,
        vault: CredentialVault,
    ) -> Dict[str, Any]:
        return {"internal": True}

    async def check_health(
        self,
        *,
        account: ConnectedAccount,
        vault: CredentialVault,
    ) -> bool:
        return True

    async def publish(
        self,
        *,
        db: AsyncSession,
        payload: PlatformPayload,
        account: ConnectedAccount,
        vault: CredentialVault,
        media_assets: List[Dict[str, Any]],
    ) -> ProviderPublishResult:
        pkg_res = await db.execute(
            select(PublishingPackage).where(PublishingPackage.id == payload.package_id)
        )
        package = pkg_res.scalar_one_or_none()
        if not package:
            return ProviderPublishResult(
                success=False,
                error_message=f"PublishingPackage '{payload.package_id}' not found.",
            )

        slug = (payload.adapted_title or package.canonical_title or "story").lower()
        slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-")[:60]
        canonical_url = f"https://news9.example.com/stories/{slug}-{package.id[:8]}"

        # If linked to a Phase 2 Story, update editorial state
        if package.story_id:
            story_res = await db.execute(
                select(Story).where(
                    Story.id == package.story_id,
                    Story.tenant_id == package.tenant_id,
                )
            )
            story = story_res.scalar_one_or_none()
            if story:
                if story.status != EditorialState.PUBLISHED.value:
                    story.status = EditorialState.PUBLISHED.value
                    story.updated_at = utc_now()

        return ProviderPublishResult(
            success=True,
            external_id=str(package.story_id or package.id),
            url=canonical_url,
            raw_response={"status": "PUBLISHED", "canonical_url": canonical_url},
        )
