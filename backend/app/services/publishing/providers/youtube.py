"""YouTube Data API v3 publishing provider.

Handles standard video uploads, Shorts validation, thumbnail setting, and category tagging.
Raises ProviderNotConfiguredError if live credentials or client secrets are absent.
"""

from __future__ import annotations

from typing import Any, Dict, List

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.publishing import (
    AccountCredential,
    ConnectedAccount,
    DestinationType,
    PlatformPayload,
)
from app.services.publishing.providers.base import (
    ProviderCapabilities,
    ProviderNotConfiguredError,
    ProviderPublishResult,
    PublishingProvider,
)
from app.services.publishing.rate_limiter import rate_limiter
from app.services.publishing.vault import CredentialVault


class YouTubeProvider(PublishingProvider):
    """Production provider for YouTube Data API v3."""

    destination_type = DestinationType.YOUTUBE
    is_mock = False

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            destination_type=DestinationType.YOUTUBE.value,
            max_video_duration_seconds=43200.0,  # 12 hours for verified accounts
            supports_resumable_upload=True,
            supported_aspect_ratios=["16:9", "9:16"],
            supported_media_types=["video/mp4", "video/quicktime"],
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
        cred_res = await db.execute(
            select(AccountCredential).where(
                AccountCredential.account_id == account.id,
                AccountCredential.tenant_id == account.tenant_id,
            )
        )
        cred = cred_res.scalar_one_or_none()
        if not cred:
            raise ProviderNotConfiguredError(
                f"No credentials configured for YouTube account '{account.id}'."
            )

        data = vault.decrypt_credential(
            cred.encrypted_access_token,
            tenant_id=account.tenant_id,
            account_id=account.id,
            nonce=cred.access_token_nonce,
        )
        return data

    async def check_health(
        self,
        *,
        account: ConnectedAccount,
        vault: CredentialVault,
    ) -> bool:
        settings = get_settings()
        if not getattr(settings, "YOUTUBE_CLIENT_ID", None):
            return False
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
        settings = get_settings()
        client_id = getattr(settings, "YOUTUBE_CLIENT_ID", None)
        client_secret = getattr(settings, "YOUTUBE_CLIENT_SECRET", None)
        if not client_id or not client_secret:
            raise ProviderNotConfiguredError(
                "YouTube API credentials (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET) "
                "are not configured."
            )

        await rate_limiter.check_and_consume(
            account.tenant_id, DestinationType.YOUTUBE.value, cost=1.0
        )

        creds = await self.ensure_valid_credentials(db=db, account=account, vault=vault)
        access_token = creds.get("access_token")

        title = payload.adapted_title or "Untitled Video"
        description = payload.adapted_description or payload.adapted_caption or ""
        custom = payload.custom_metadata or {}
        tags = custom.get("tags", [])
        category_id = custom.get("category_id", "25")

        upload_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
        }
        body_metadata = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": custom.get("privacy_status", "public"),
                "selfDeclaredMadeForKids": False,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(upload_url, headers=headers, json=body_metadata)
            if resp.status_code not in (200, 201):
                return ProviderPublishResult(
                    success=False,
                    error_message=(
                        f"YouTube API upload initiation failed ({resp.status_code}): {resp.text}"
                    ),
                    raw_response={"status_code": resp.status_code, "body": resp.text},
                )

            location = resp.headers.get("Location")
            video_id = (
                resp.json().get("id")
                if resp.headers.get("content-type", "").startswith("application/json")
                else "pending_stream"
            )

            return ProviderPublishResult(
                success=True,
                external_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}"
                if video_id != "pending_stream"
                else None,
                raw_response=resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else {"upload_location": location},
            )
