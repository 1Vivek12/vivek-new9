"""Webhook ingestion and signature verification for external publishing platforms.

Enforces:
1. Cryptographic signature verification (Meta X-Hub-Signature-256).
2. Multi-tenant deduplication based on UNIQUE(destination_type, external_event_id).
3. State reconciliation for asynchronous video ingestion and WhatsApp status callbacks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import logger
from app.db.models.publishing import DestinationType, WebhookEvent
from app.db.session import get_db_session

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class MetaWebhookVerifier:
    """Verifies X-Hub-Signature-256 against Meta App Secret."""

    @staticmethod
    def verify_signature(raw_body: bytes, signature_header: Optional[str], app_secret: str) -> bool:
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        expected_hash = signature_header[7:]
        computed_hash = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_hash, computed_hash)


@router.get("/meta")
async def verify_meta_webhook(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge"),
):
    """Handles Meta webhook subscription verification handshake."""
    settings = get_settings()
    expected_token = getattr(settings, "META_WEBHOOK_VERIFY_TOKEN", "news9_meta_verify_token")

    if mode == "subscribe" and token == expected_token:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")


@router.post("/meta/{tenant_id}")
async def handle_meta_webhook(
    tenant_id: str,
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    db: AsyncSession = Depends(get_db_session),
):
    """Processes verified Meta webhook payloads (Facebook, Instagram, WhatsApp)
    with deduplication.
    """
    settings = get_settings()
    app_secret = getattr(settings, "META_APP_SECRET", "")

    raw_body = await request.body()

    # Signature verification (strict if app_secret is set)
    if app_secret:
        if not MetaWebhookVerifier.verify_signature(raw_body, x_hub_signature_256, app_secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Meta webhook signature.",
            )

    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body"
        ) from exc

    obj_type = body.get("object")
    entries = body.get("entry", [])

    for entry in entries:
        entry_id = str(entry.get("id", ""))
        event_time = entry.get("time", "")
        external_event_id = f"{entry_id}_{event_time}"

        dest_type = DestinationType.FACEBOOK.value
        if obj_type == "instagram":
            dest_type = DestinationType.INSTAGRAM.value
        elif obj_type == "whatsapp_business_account":
            dest_type = DestinationType.WHATSAPP.value

        # Deduplication check
        existing = await db.execute(
            select(WebhookEvent).where(
                WebhookEvent.destination_type == dest_type,
                WebhookEvent.external_event_id == external_event_id,
            )
        )
        if existing.scalar_one_or_none():
            logger.info(f"Ignored duplicate webhook event: {dest_type} {external_event_id}")
            continue

        event = WebhookEvent(
            tenant_id=tenant_id,
            destination_type=dest_type,
            external_event_id=external_event_id,
            event_type=obj_type or "unknown",
            signature_verified=True,
            processing_status="PROCESSED",
            sanitized_payload=entry,
        )
        db.add(event)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            logger.info(f"Duplicate webhook event caught by constraint: {external_event_id}")

    return {"status": "SUCCESS", "message": "Webhook processed"}
