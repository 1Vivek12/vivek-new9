"""News 9 Website internal publishing provider.

Handles direct publishing to the News 9 web content management system, transitioning
Phase 2 Story records to EditorialState.PUBLISHED, generating SEO canonical URLs,
and recording published items.
"""

from __future__ import annotations

from typing import Any, Dict, List

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
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
    ProviderNotConfiguredError,
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
        settings = get_settings()
        cms_url = getattr(settings, "WEBSITE_CMS_PUBLISH_URL", None)
        if not cms_url:
            raise ProviderNotConfiguredError(
                "News 9 Website CMS publishing endpoint (WEBSITE_CMS_PUBLISH_URL) "
                "is not configured."
            )
        return {"cms_url": cms_url}

    async def check_health(
        self,
        *,
        account: ConnectedAccount,
        vault: CredentialVault,
    ) -> bool:
        settings = get_settings()
        cms_url = getattr(settings, "WEBSITE_CMS_PUBLISH_URL", None)
        return bool(cms_url)

    async def publish(
        self,
        *,
        db: AsyncSession,
        payload: PlatformPayload,
        account: ConnectedAccount,
        vault: CredentialVault,
        media_assets: List[Dict[str, Any]],
    ) -> ProviderPublishResult:
        settings = get_settings()
        cms_url = getattr(settings, "WEBSITE_CMS_PUBLISH_URL", None)
        if not cms_url:
            raise ProviderNotConfiguredError(
                "News 9 Website CMS publishing endpoint (WEBSITE_CMS_PUBLISH_URL) "
                "is not configured."
            )

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

        api_key = getattr(settings, "WEBSITE_CMS_API_KEY", "") or ""
        post_data = {
            "story_id": package.story_id,
            "package_id": package.id,
            "title": payload.adapted_title or package.canonical_title,
            "content": payload.adapted_description or package.canonical_description,
            "slug": slug,
            "tags": package.tags,
            "published_at": utc_now().isoformat(),
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(cms_url, headers=headers, json=post_data)
            except httpx.HTTPError as exc:
                return ProviderPublishResult(
                    success=False,
                    error_message=f"Website CMS network error: {str(exc)}",
                )

            if resp.status_code not in (200, 201):
                return ProviderPublishResult(
                    success=False,
                    error_message=(
                        f"Website CMS rejected publication ({resp.status_code}): {resp.text}"
                    ),
                    raw_response={"status_code": resp.status_code, "body": resp.text},
                )

            res_data = (
                resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            canonical_url = res_data.get("canonical_url") or res_data.get("url")
            external_cms_id = str(
                res_data.get("id")
                or res_data.get("story_id")
                or package.story_id
                or package.id
            )

            if not canonical_url:
                return ProviderPublishResult(
                    success=False,
                    error_message=(
                        "Website CMS confirmed publication but returned no canonical URL."
                    ),
                    raw_response=res_data,
                )

            # ONLY after real downstream system confirms publication, update Story state
            if package.story_id:
                story_res = await db.execute(
                    select(Story).where(
                        Story.id == package.story_id,
                        Story.tenant_id == package.tenant_id,
                    )
                )
                story = story_res.scalar_one_or_none()
                if story and story.status != EditorialState.PUBLISHED.value:
                    story.status = EditorialState.PUBLISHED.value
                    story.updated_at = utc_now()

            return ProviderPublishResult(
                success=True,
                external_id=external_cms_id,
                url=canonical_url,
                raw_response=res_data,
            )
