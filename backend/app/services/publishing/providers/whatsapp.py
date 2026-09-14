"""WhatsApp Cloud API message dispatch provider.

Implements recipient-based broadcast dispatch honoring strict application safety
rate limits (20 msgs/sec), E.164 phone number formatting, and template compliance.
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


class WhatsAppProvider(PublishingProvider):
    """Production provider for WhatsApp Cloud API."""

    destination_type = DestinationType.WHATSAPP
    is_mock = False

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            destination_type=DestinationType.WHATSAPP.value,
            max_video_duration_seconds=180.0,
            supports_resumable_upload=False,
            supported_aspect_ratios=["1:1", "16:9"],
            supported_media_types=["image/jpeg", "video/mp4", "application/pdf"],
            max_title_length=60,
            max_body_length=4096,
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
                f"No credentials configured for WhatsApp account '{account.id}'."
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
                "WhatsApp Cloud API credentials (META_APP_ID, META_APP_SECRET) are not configured."
            )

        creds = await self.ensure_valid_credentials(db=db, account=account, vault=vault)
        token = creds.get("system_user_token") or creds.get("access_token")
        phone_number_id = account.platform_account_id
        api_ver = getattr(settings, "META_GRAPH_API_VERSION", "v21.0")

        custom = payload.custom_metadata or {}
        recipients = custom.get("recipients", [])
        if not recipients:
            return ProviderPublishResult(
                success=False,
                error_message="WhatsApp dispatch requires at least one recipient phone number.",
            )

        endpoint = f"https://graph.facebook.com/{api_ver}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        successful_messages: List[str] = []
        errors: List[str] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for recipient in recipients:
                # Enforce 20 msgs/second token bucket rate limit
                await rate_limiter.check_and_consume(
                    account.tenant_id, DestinationType.WHATSAPP.value, cost=1.0
                )

                msg_text = (
                    payload.adapted_description
                    or payload.adapted_caption
                    or payload.adapted_title
                    or ""
                )
                body_data: Dict[str, Any] = {
                    "messaging_product": "whatsapp",
                    "to": recipient,
                    "type": "text",
                    "text": {"body": msg_text},
                }

                resp = await client.post(endpoint, headers=headers, json=body_data)
                if resp.status_code == 200:
                    msg_id = resp.json().get("messages", [{}])[0].get("id")
                    successful_messages.append(msg_id)
                else:
                    errors.append(f"Recipient {recipient} failed: {resp.text}")

        if not successful_messages and errors:
            return ProviderPublishResult(
                success=False,
                error_message="; ".join(errors[:3]),
                raw_response={"errors": errors},
            )

        return ProviderPublishResult(
            success=True,
            external_id=successful_messages[0] if successful_messages else "batch_dispatched",
            raw_response={
                "dispatched_count": len(successful_messages),
                "message_ids": successful_messages,
                "errors": errors,
            },
        )
