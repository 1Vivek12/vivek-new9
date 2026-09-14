"""Facebook Graph API publishing provider.

Handles Facebook Page posts and video uploads via the configured META_GRAPH_API_VERSION.
Raises ProviderNotConfiguredError if live Meta app credentials are not configured.
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


class FacebookProvider(PublishingProvider):
    """Production provider for Facebook Pages via Meta Graph API."""

    destination_type = DestinationType.FACEBOOK
    is_mock = False

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            destination_type=DestinationType.FACEBOOK.value,
            max_video_duration_seconds=14400.0,  # 240 minutes
            supports_resumable_upload=True,
            supported_aspect_ratios=["16:9", "1:1", "9:16", "4:5"],
            supported_media_types=["video/mp4", "image/jpeg", "image/png"],
            max_title_length=255,
            max_body_length=63206,
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
                f"No credentials configured for Facebook account '{account.id}'."
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
        if not getattr(settings, "META_APP_ID", None):
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
        app_id = getattr(settings, "META_APP_ID", None)
        app_secret = getattr(settings, "META_APP_SECRET", None)
        if not app_id or not app_secret:
            raise ProviderNotConfiguredError(
                "Meta Graph API credentials (META_APP_ID, META_APP_SECRET) are not configured."
            )

        await rate_limiter.check_and_consume(
            account.tenant_id, DestinationType.FACEBOOK.value, cost=1.0
        )

        creds = await self.ensure_valid_credentials(db=db, account=account, vault=vault)
        token = creds.get("page_access_token") or creds.get("access_token")
        page_id = account.platform_account_id
        api_ver = getattr(settings, "META_GRAPH_API_VERSION", "v21.0")

        url = f"https://graph.facebook.com/{api_ver}/{page_id}/feed"
        message = (
            payload.adapted_description or payload.adapted_caption or payload.adapted_title or ""
        )
        data: Dict[str, Any] = {
            "access_token": token,
            "message": message,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, data=data)
            res_json = resp.json()

            if resp.status_code != 200:
                error_msg = res_json.get("error", {}).get("message", resp.text)
                return ProviderPublishResult(
                    success=False,
                    error_message=f"Facebook API error ({resp.status_code}): {error_msg}",
                    raw_response=res_json,
                )

            post_id = res_json.get("id")
            return ProviderPublishResult(
                success=True,
                external_id=post_id,
                url=f"https://www.facebook.com/{post_id}" if post_id else None,
                raw_response=res_json,
            )
