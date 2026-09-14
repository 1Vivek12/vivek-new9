"""Phase 6 Publishing & Distribution REST API endpoints."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import check_permission
from app.core.tenant import TenantContext, get_tenant_context
from app.db.base import utc_now
from app.db.models.media import MediaAsset
from app.db.models.publishing import (
    AccountCredential,
    ConnectedAccount,
    DestinationType,
    PublishedItem,
    PublishingDestination,
    PublishingJob,
    PublishingPackage,
)
from app.db.session import get_db_session
from app.schemas.publishing import (
    ConnectedAccountResponse,
    CreatePublishingPackageRequest,
    DestinationResponse,
    PlatformPayloadResponse,
    PublishedItemResponse,
    PublishingApprovalEventResponse,
    PublishingApprovalRequest,
    PublishingJobResponse,
    PublishingPackageResponse,
    SchedulePublishRequest,
    ValidationResultResponse,
)
from app.services.publishing.delivery import DeliverySecurityError, ExternalMediaDeliveryService
from app.services.publishing.package_builder import (
    ManifestTamperedError,
    PublishingPackageService,
    PublishingWorkflowError,
)
from app.services.publishing.validator import PrePublishValidator
from app.services.publishing.vault import get_credential_vault
from app.worker.publishing_tasks import execute_publish_pipeline

router = APIRouter(prefix="/publishing", tags=["Publishing & Distribution"])


# ==========================================
# 1. DESTINATIONS
# ==========================================


@router.get("/destinations", response_model=List[DestinationResponse])
async def list_destinations(
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    check_permission(context, "VIEW_PUBLISHING")
    result = await db.execute(
        select(PublishingDestination).where(
            PublishingDestination.tenant_id == context.tenant_id,
            PublishingDestination.is_active.is_(True),
        )
    )
    destinations = result.scalars().all()

    # Seed default destinations for tenant if none exist yet
    if not destinations:
        default_types = [
            (DestinationType.YOUTUBE.value, "YouTube"),
            (DestinationType.FACEBOOK.value, "Facebook"),
            (DestinationType.INSTAGRAM.value, "Instagram"),
            (DestinationType.WHATSAPP.value, "WhatsApp"),
            (DestinationType.WEBSITE.value, "News 9 Website"),
        ]
        new_dests = []
        for dtype, name in default_types:
            d = PublishingDestination(
                tenant_id=context.tenant_id,
                destination_type=dtype,
                display_name=name,
                is_active=True,
                config_payload={},
            )
            db.add(d)
            new_dests.append(d)
        await db.commit()
        for d in new_dests:
            await db.refresh(d)
        return new_dests

    return destinations


# ==========================================
# 2. CONNECTED ACCOUNTS
# ==========================================


@router.get("/accounts", response_model=List[ConnectedAccountResponse])
async def list_connected_accounts(
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    check_permission(context, "VIEW_PUBLISHING")
    result = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.tenant_id == context.tenant_id,
            ConnectedAccount.is_deleted.is_(False),
        )
    )
    return result.scalars().all()


@router.post("/accounts/connect", response_model=Dict[str, Any])
async def initiate_account_connection(
    payload: Dict[str, Any],
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """Initiates account connection via OAuth or manual API key configuration."""
    check_permission(context, "MANAGE_DESTINATIONS")
    destination_id = payload.get("destination_id")
    account_type = payload.get("account_type", "CHANNEL")
    platform_account_id = payload.get("platform_account_id")
    account_name = payload.get("account_name", "Connected Channel")
    access_token = payload.get("access_token")

    dest_res = await db.execute(
        select(PublishingDestination).where(
            PublishingDestination.id == destination_id,
            PublishingDestination.tenant_id == context.tenant_id,
        )
    )
    destination = dest_res.scalar_one_or_none()
    if not destination:
        raise HTTPException(status_code=404, detail="Publishing destination not found")

    vault = get_credential_vault()

    # Controlled Resurrection check: Check if soft-deleted account already exists
    existing_res = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.tenant_id == context.tenant_id,
            ConnectedAccount.destination_id == destination_id,
            ConnectedAccount.platform_account_id == platform_account_id,
        )
    )
    account = existing_res.scalar_one_or_none()

    if account:
        # Resurrect soft-deleted account
        account.is_deleted = False
        account.connection_status = "CONNECTED"
        account.account_name = account_name
        account.account_type = account_type
        account.last_health_check_at = utc_now()
        account.connected_by_user_id = context.user_id
    else:
        account = ConnectedAccount(
            tenant_id=context.tenant_id,
            destination_id=destination_id,
            account_type=account_type,
            platform_account_id=platform_account_id,
            account_name=account_name,
            account_metadata=payload.get("account_metadata", {}),
            connection_status="CONNECTED",
            last_health_check_at=utc_now(),
            connected_by_user_id=context.user_id,
            is_deleted=False,
        )
        db.add(account)

    await db.flush()

    # If access token was provided, encrypt with AES-256-GCM
    if access_token:
        encrypted_token, nonce, key_ver = vault.encrypt_credential(
            {"access_token": access_token},
            tenant_id=context.tenant_id,
            account_id=account.id,
        )

        cred_res = await db.execute(
            select(AccountCredential).where(AccountCredential.account_id == account.id)
        )
        cred = cred_res.scalar_one_or_none()
        if not cred:
            cred = AccountCredential(
                tenant_id=context.tenant_id,
                account_id=account.id,
                encrypted_access_token=encrypted_token,
                access_token_nonce=nonce,
                key_version=key_ver,
                scopes=payload.get("scopes", []),
            )
            db.add(cred)
        else:
            cred.encrypted_access_token = encrypted_token
            cred.access_token_nonce = nonce
            cred.key_version = key_ver
            cred.last_refreshed_at = utc_now()

    await db.commit()
    await db.refresh(account)

    return {
        "status": "SUCCESS",
        "account_id": account.id,
        "connection_status": account.connection_status,
    }


@router.delete("/accounts/{account_id}")
async def disconnect_account(
    account_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    check_permission(context, "MANAGE_DESTINATIONS")
    acc_res = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.id == account_id,
            ConnectedAccount.tenant_id == context.tenant_id,
        )
    )
    account = acc_res.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Connected account not found")

    # Soft delete to preserve historical published items and audit logs
    account.is_deleted = True
    account.connection_status = "REVOKED"
    await db.commit()
    return {"status": "SUCCESS", "message": "Account disconnected"}


# ==========================================
# 3. PUBLISHING PACKAGES & PAYLOADS
# ==========================================


@router.post("/packages", response_model=PublishingPackageResponse)
async def create_publishing_package(
    payload: CreatePublishingPackageRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    check_permission(context, "CREATE_PACKAGE")

    try:
        package = await PublishingPackageService.create_package(
            db,
            tenant_id=context.tenant_id,
            creator_id=context.user_id,
            story_id=payload.story_id,
            story_version_id=payload.story_version_id,
            canonical_title=payload.canonical_title or "Untitled Package",
            canonical_description=payload.canonical_description or "",
            canonical_caption=payload.canonical_caption,
            tags=payload.tags,
            primary_media_asset_id=payload.primary_media_asset_id,
            primary_derivative_id=payload.primary_derivative_id,
            visual_asset_id=payload.visual_asset_id,
            subtitle_track_id=payload.subtitle_track_id,
        )
    except PublishingWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Auto-create platform payloads for requested destination types if accounts provided
    if payload.account_ids:
        for acc_id in payload.account_ids:
            acc_res = await db.execute(
                select(ConnectedAccount).where(
                    ConnectedAccount.id == acc_id,
                    ConnectedAccount.tenant_id == context.tenant_id,
                    ConnectedAccount.is_deleted.is_(False),
                )
            )
            acc = acc_res.scalar_one_or_none()
            if acc:
                dest_res = await db.execute(
                    select(PublishingDestination).where(
                        PublishingDestination.id == acc.destination_id
                    )
                )
                dest = dest_res.scalar_one_or_none()
                dest_type = dest.destination_type if dest else DestinationType.WEBSITE.value

                await PublishingPackageService.add_or_update_platform_payload(
                    db,
                    package_id=package.id,
                    tenant_id=context.tenant_id,
                    destination_type=dest_type,
                    account_id=acc.id,
                    adapted_title=package.canonical_title,
                    adapted_description=package.canonical_description,
                    adapted_caption=package.canonical_caption or "",
                    selected_derivative_id=package.primary_derivative_id,
                    selected_thumbnail_id=package.visual_asset_id,
                )

    await db.commit()

    # Re-fetch with payloads
    pkg_res = await db.execute(
        select(PublishingPackage)
        .options(selectinload(PublishingPackage.payloads))
        .where(PublishingPackage.id == package.id)
    )
    loaded_pkg = pkg_res.scalar_one()
    return loaded_pkg


@router.get("/packages", response_model=List[PublishingPackageResponse])
async def list_publishing_packages(
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    check_permission(context, "VIEW_PUBLISHING")
    result = await db.execute(
        select(PublishingPackage)
        .options(selectinload(PublishingPackage.payloads))
        .where(
            PublishingPackage.tenant_id == context.tenant_id,
            PublishingPackage.is_deleted.is_(False),
        )
        .order_by(desc(PublishingPackage.created_at))
    )
    return result.scalars().all()


@router.get("/packages/{package_id}", response_model=PublishingPackageResponse)
async def get_publishing_package(
    package_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    check_permission(context, "VIEW_PUBLISHING")
    result = await db.execute(
        select(PublishingPackage)
        .options(selectinload(PublishingPackage.payloads))
        .where(
            PublishingPackage.id == package_id,
            PublishingPackage.tenant_id == context.tenant_id,
            PublishingPackage.is_deleted.is_(False),
        )
    )
    package = result.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="PublishingPackage not found")
    return package


@router.post("/packages/{package_id}/payloads", response_model=PlatformPayloadResponse)
async def update_platform_payload(
    package_id: str,
    payload_data: Dict[str, Any],
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """Adds or updates a platform payload, automatically invalidating any prior approval."""
    check_permission(context, "CREATE_PACKAGE")

    account_id = payload_data.get("account_id")
    destination_type = payload_data.get("destination_type", "WEBSITE")

    if not account_id:
        raise HTTPException(status_code=400, detail="account_id is required")

    try:
        updated_payload = await PublishingPackageService.add_or_update_platform_payload(
            db,
            package_id=package_id,
            tenant_id=context.tenant_id,
            destination_type=destination_type,
            account_id=account_id,
            adapted_title=payload_data.get("adapted_title", ""),
            adapted_description=payload_data.get("adapted_description", ""),
            adapted_caption=payload_data.get("adapted_caption", ""),
            target_aspect_ratio=payload_data.get("target_aspect_ratio", "16:9"),
            selected_derivative_id=payload_data.get("selected_derivative_id"),
            selected_thumbnail_id=payload_data.get("selected_thumbnail_id"),
            custom_metadata=payload_data.get("custom_metadata", {}),
        )
        await db.commit()
        await db.refresh(updated_payload)
        return updated_payload
    except PublishingWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ==========================================
# 4. VALIDATION & APPROVAL GATES
# ==========================================


@router.post("/packages/{package_id}/validate", response_model=ValidationResultResponse)
async def validate_publishing_package(
    package_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    check_permission(context, "VIEW_PUBLISHING")
    pkg_res = await db.execute(
        select(PublishingPackage)
        .options(selectinload(PublishingPackage.payloads))
        .where(
            PublishingPackage.id == package_id,
            PublishingPackage.tenant_id == context.tenant_id,
            PublishingPackage.is_deleted.is_(False),
        )
    )
    package = pkg_res.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="PublishingPackage not found")

    # Fetch media assets
    media_assets_list = []
    media_ids = []
    if package.primary_media_asset_id:
        media_ids.append(package.primary_media_asset_id)
    if package.visual_asset_id:
        media_ids.append(package.visual_asset_id)

    if media_ids:
        m_res = await db.execute(
            select(MediaAsset).where(
                MediaAsset.id.in_(media_ids),
                MediaAsset.tenant_id == context.tenant_id,
            )
        )
        for a in m_res.scalars().all():
            aspect = f"{a.width}:{a.height}" if a.width and a.height else "16:9"
            media_assets_list.append(
                {
                    "asset_id": a.id,
                    "storage_path": a.storage_key,
                    "rights_metadata": a.rights_metadata,
                    "duration_seconds": a.duration or 0.0,
                    "aspect_ratio": aspect,
                }
            )

    # Prepare payload dicts
    payload_dicts = []
    account_ids = []
    for p in package.payloads:
        account_ids.append(p.account_id)
        payload_dicts.append(
            {
                "account_id": p.account_id,
                "destination_type": p.destination_type,
                "adapted_title": p.adapted_title,
                "adapted_description": p.adapted_description,
                "adapted_caption": p.adapted_caption,
                "target_aspect_ratio": p.target_aspect_ratio,
                "selected_derivative_id": p.selected_derivative_id,
                "custom_metadata": p.custom_metadata,
            }
        )

    # Fetch account statuses
    acc_map = {}
    if account_ids:
        acc_res = await db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.id.in_(account_ids),
                ConnectedAccount.tenant_id == context.tenant_id,
            )
        )
        for acc in acc_res.scalars().all():
            acc_map[acc.id] = acc.connection_status

    validator = PrePublishValidator()
    val_result = validator.validate_package(
        canonical_title=package.canonical_title,
        canonical_description=package.canonical_description,
        media_assets=media_assets_list,
        platform_payloads=payload_dicts,
        account_status_map=acc_map,
    )

    _, manifest_hash = await PublishingPackageService.get_canonical_manifest_and_hash(db, package)

    validation_errors = [i.message for i in val_result.issues if i.severity == "ERROR"]
    payload_validations = {}
    for p in package.payloads:
        p_errs = [
            i.message
            for i in val_result.issues
            if i.severity == "ERROR"
            and (i.destination_type == p.destination_type or i.field == p.destination_type)
        ]
        payload_validations[p.id] = p_errs

    return ValidationResultResponse(
        package_id=package.id,
        is_valid=val_result.is_valid,
        manifest_hash=manifest_hash,
        validation_errors=validation_errors,
        payload_validations=payload_validations,
    )


@router.post("/packages/{package_id}/approve", response_model=PublishingApprovalEventResponse)
async def approve_publishing_package(
    package_id: str,
    approval_data: PublishingApprovalRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """Enforces mandatory human editorial approval. Appends immutable event to ledger."""
    check_permission(context, "APPROVE_PUBLISHING")

    # Anti-bot/Anti-AI check: ensure user_id is a real human user
    if (
        context.user_id in ("system", "ai_agent", "automated_bot")
        or context.user_id.startswith("bot_")
        or context.user_id.startswith("ai_")
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Autonomous or AI-driven approval is strictly forbidden. "
                "Approval must be performed by a human editor."
            ),
        )

    try:
        if approval_data.action == "APPROVE":
            event = await PublishingPackageService.approve_package(
                db,
                package_id=package_id,
                tenant_id=context.tenant_id,
                approver_id=context.user_id,
                notes=approval_data.rejection_reason,
            )
        else:
            if not approval_data.rejection_reason or not approval_data.rejection_reason.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Rejection reason is mandatory and must not be empty.",
                )
            event = await PublishingPackageService.reject_package(
                db,
                package_id=package_id,
                tenant_id=context.tenant_id,
                approver_id=context.user_id,
                rejection_reason=approval_data.rejection_reason.strip(),
            )
        await db.commit()
        await db.refresh(event)
        return event
    except PublishingWorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ==========================================
# 5. DISPATCH & SCHEDULING
# ==========================================


@router.post("/packages/{package_id}/publish", response_model=PublishingJobResponse)
async def publish_package(
    package_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """Dispatches publishing execution after verifying human approval."""
    check_permission(context, "TRIGGER_PUBLISH")

    pkg_res = await db.execute(
        select(PublishingPackage)
        .options(selectinload(PublishingPackage.payloads))
        .where(
            PublishingPackage.id == package_id,
            PublishingPackage.tenant_id == context.tenant_id,
            PublishingPackage.is_deleted.is_(False),
        )
    )
    package = pkg_res.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="PublishingPackage not found")

    if package.status != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot publish package in status '{package.status}'. "
                "Must be in APPROVED status."
            ),
        )

    # Manifest re-verification before queuing
    try:
        await PublishingPackageService.reverify_manifest_at_dispatch(db, package)
    except ManifestTamperedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not package.payloads:
        raise HTTPException(status_code=400, detail="Package has no platform payloads to publish")

    primary_account_id = package.payloads[0].account_id
    _, manifest_hash = await PublishingPackageService.get_canonical_manifest_and_hash(db, package)

    # Stable idempotency key
    idempotency_raw = f"{context.tenant_id}:{package.id}:{primary_account_id}:{manifest_hash}"
    idempotency_key = hashlib.sha256(idempotency_raw.encode("utf-8")).hexdigest()

    # Create job
    job = PublishingJob(
        tenant_id=context.tenant_id,
        package_id=package.id,
        account_id=primary_account_id,
        publication_idempotency_key=idempotency_key,
        job_status="QUEUED",
        attempts=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Execute pipeline synchronously (or through celery in prod worker)
    await execute_publish_pipeline(
        tenant_id=context.tenant_id,
        package_id=package.id,
        job_id=job.id,
        db_session=db,
    )

    await db.refresh(job)
    return job


@router.post("/packages/{package_id}/schedule", response_model=Dict[str, Any])
async def schedule_package(
    package_id: str,
    payload: SchedulePublishRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    check_permission(context, "TRIGGER_PUBLISH")
    pkg_res = await db.execute(
        select(PublishingPackage).where(
            PublishingPackage.id == package_id,
            PublishingPackage.tenant_id == context.tenant_id,
            PublishingPackage.is_deleted.is_(False),
        )
    )
    package = pkg_res.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="PublishingPackage not found")

    if package.status != "APPROVED":
        raise HTTPException(status_code=400, detail="Package must be APPROVED before scheduling")

    now = datetime.now(timezone.utc)
    if payload.scheduled_at <= now:
        raise HTTPException(status_code=400, detail="scheduled_at must be in the future")

    package.status = "SCHEDULED"
    await db.commit()
    return {
        "status": "SUCCESS",
        "message": "Package scheduled",
        "scheduled_at": payload.scheduled_at,
    }


@router.post("/packages/{package_id}/cancel", response_model=Dict[str, Any])
async def cancel_package_publication(
    package_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    check_permission(context, "CANCEL_PUBLISH")
    pkg_res = await db.execute(
        select(PublishingPackage).where(
            PublishingPackage.id == package_id,
            PublishingPackage.tenant_id == context.tenant_id,
            PublishingPackage.is_deleted.is_(False),
        )
    )
    package = pkg_res.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="PublishingPackage not found")

    if package.status in ("PUBLISHING", "PUBLISHED"):
        raise HTTPException(
            status_code=400, detail=f"Cannot cancel package in status '{package.status}'"
        )

    package.status = "DRAFT"
    await db.commit()
    return {"status": "SUCCESS", "message": "Publication cancelled"}


# ==========================================
# 6. JOBS & PUBLISHED ITEMS
# ==========================================


@router.get("/jobs/{job_id}", response_model=PublishingJobResponse)
async def get_publishing_job(
    job_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    check_permission(context, "VIEW_PUBLISHING")
    result = await db.execute(
        select(PublishingJob).where(
            PublishingJob.id == job_id,
            PublishingJob.tenant_id == context.tenant_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="PublishingJob not found")
    return job


@router.get("/published-items", response_model=List[PublishedItemResponse])
async def list_published_items(
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    check_permission(context, "VIEW_PUBLISHING")
    result = await db.execute(
        select(PublishedItem)
        .where(PublishedItem.tenant_id == context.tenant_id)
        .order_by(desc(PublishedItem.published_at))
    )
    return result.scalars().all()


# ==========================================
# 7. EXTERNAL MEDIA DELIVERY BRIDGE (INSTAGRAM)
# ==========================================


@router.get("/delivery/{token}")
async def serve_external_media_delivery(
    token: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Secure, time-limited, HMAC-signed public media download endpoint for Instagram ingestion."""
    delivery_service = ExternalMediaDeliveryService()
    try:
        file_path, tenant_id, asset_id = delivery_service.verify_and_resolve_file(token)
    except DeliverySecurityError as exc:
        raise HTTPException(
            status_code=403, detail=f"Media delivery rejected: {str(exc)}"
        ) from exc

    # Verify rights in DB
    asset_res = await db.execute(
        select(MediaAsset).where(MediaAsset.id == asset_id, MediaAsset.tenant_id == tenant_id)
    )
    asset = asset_res.scalar_one_or_none()
    if asset:
        try:
            delivery_service.verify_and_resolve_file(
                token, asset_rights_metadata=asset.rights_metadata
            )
        except Exception as exc:
            raise HTTPException(
                status_code=403, detail=f"Rights clearance check failed: {str(exc)}"
            ) from exc

    media_type = "video/mp4" if str(file_path).lower().endswith(".mp4") else "image/jpeg"
    return FileResponse(path=str(file_path), media_type=media_type)
