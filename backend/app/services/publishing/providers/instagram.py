"""Instagram Graph API publishing provider.

Implements Instagram's two-step media container publishing flow:
1. Container creation using a secure, HMAC-signed URL from ExternalMediaDeliveryService.
2. Polling container processing status until FINISHED.
3. Media publishing via creation_id.
"""

from __future__ import annotations

import asyncio
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
from app.services.publishing.delivery import ExternalMediaDeliveryService
from app.services.publishing.providers.base import (
    ProviderCapabilities,
    ProviderNotConfiguredError,
    ProviderPublishResult,
    PublishingProvider,
)
from app.services.publishing.rate_limiter import rate_limiter
from app.services.publishing.vault import CredentialVault


class InstagramProvider(PublishingProvider):
    """Production provider for Instagram via Meta Graph API."""

    destination_type = DestinationType.INSTAGRAM
    is_mock = False

    def __init__(self):
        self.delivery_service = ExternalMediaDeliveryService()

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            destination_type=DestinationType.INSTAGRAM.value,
            max_video_duration_seconds=90.0,  # Reels standard limit
            supports_resumable_upload=False,
            supported_aspect_ratios=["9:16", "1:1", "4:5"],
            supported_media_types=["video/mp4", "image/jpeg"],
            max_title_length=100,
            max_body_length=2200,
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
                f"No credentials configured for Instagram account '{account.id}'."
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
            account.tenant_id, DestinationType.INSTAGRAM.value, cost=1.0
        )

        creds = await self.ensure_valid_credentials(db=db, account=account, vault=vault)
        token = creds.get("access_token")
        ig_user_id = account.platform_account_id
        api_ver = getattr(settings, "META_GRAPH_API_VERSION", "v21.0")

        if not media_assets:
            return ProviderPublishResult(
                success=False,
                error_message="Instagram publication requires at least one media asset.",
            )

        primary_asset = media_assets[0]
        delivery_url = self.delivery_service.get_delivery_url(
            tenant_id=account.tenant_id,
            asset_id=str(primary_asset.get("asset_id") or primary_asset.get("id")),
            storage_path=str(primary_asset.get("storage_path")),
        )

        caption = payload.adapted_caption or payload.adapted_description or ""
        custom = payload.custom_metadata or {}
        media_type = "REELS" if custom.get("is_reel", True) else "VIDEO"

        async with httpx.AsyncClient(timeout=45.0) as client:
            # Step 1: Create media container
            container_url = f"https://graph.facebook.com/{api_ver}/{ig_user_id}/media"
            create_params: Dict[str, Any] = {
                "access_token": token,
                "caption": caption,
                "media_type": media_type,
                "video_url": delivery_url,
            }
            c_resp = await client.post(container_url, data=create_params)
            c_json = c_resp.json()

            if c_resp.status_code != 200:
                err_msg = c_json.get("error", {}).get("message", c_resp.text)
                return ProviderPublishResult(
                    success=False,
                    error_message=f"Instagram container creation failed: {err_msg}",
                    raw_response=c_json,
                )

            creation_id = c_json.get("id")

            # Step 2: Poll container status
            status_url = f"https://graph.facebook.com/{api_ver}/{creation_id}"
            final_status_code = None
            for _ in range(10):
                await asyncio.sleep(2.0)
                s_resp = await client.get(
                    status_url, params={"access_token": token, "fields": "status_code,status"}
                )
                s_json = s_resp.json()
                final_status_code = s_json.get("status_code")
                if final_status_code == "FINISHED":
                    break
                if final_status_code == "ERROR":
                    return ProviderPublishResult(
                        success=False,
                        error_message="Instagram video container failed processing.",
                        raw_response=s_json,
                    )

            if final_status_code != "FINISHED":
                return ProviderPublishResult(
                    success=False,
                    error_message=(
                        f"Instagram video container processing timed out without FINISHED state "
                        f"(current status: {final_status_code})."
                    ),
                    raw_response={"status_code": final_status_code},
                )

            # Step 3: Publish container
            pub_url = f"https://graph.facebook.com/{api_ver}/{ig_user_id}/media_publish"
            p_resp = await client.post(
                pub_url, data={"access_token": token, "creation_id": creation_id}
            )
            p_json = p_resp.json()

            if p_resp.status_code != 200:
                err_msg = p_json.get("error", {}).get("message", p_resp.text)
                return ProviderPublishResult(
                    success=False,
                    error_message=f"Instagram publishing failed: {err_msg}",
                    raw_response=p_json,
                )

            media_id = p_json.get("id")
            return ProviderPublishResult(
                success=True,
                external_id=media_id,
                url=f"https://www.instagram.com/p/{media_id}",
                raw_response=p_json,
            )
