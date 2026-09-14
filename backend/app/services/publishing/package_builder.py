"""Publishing Package assembly, lifecycle management, and approval ledger.

Enforces:
1. Strict multi-tenant boundaries.
2. Canonical manifest hashing and pre-flight re-verification.
3. Invalidation of approvals whenever content or payloads are modified.
4. Append-only approval ledger (PublishingApprovalEvent).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models.media import MediaAsset
from app.db.models.publishing import (
    PlatformPayload,
    PublishingApprovalEvent,
    PublishingPackage,
)
from app.db.models.story import Story
from app.db.models.version import StoryVersion
from app.services.publishing.manifest import build_publication_manifest


class PublishingWorkflowError(Exception):
    """Raised on invalid publishing lifecycle state transitions."""

    pass


class ManifestTamperedError(PublishingWorkflowError):
    """Raised when dispatch-time manifest hash does not match approved manifest hash."""

    pass


class PublishingPackageService:
    """Manages creation, adaptation mutation, approval, and dispatch validation."""

    @staticmethod
    async def create_package(
        db: AsyncSession,
        *,
        tenant_id: str,
        creator_id: str,
        story_id: str,
        story_version_id: str,
        canonical_title: str,
        canonical_description: str,
        canonical_caption: Optional[str] = None,
        tags: Optional[List[str]] = None,
        primary_media_asset_id: Optional[str] = None,
        primary_derivative_id: Optional[str] = None,
        visual_asset_id: Optional[str] = None,
        subtitle_track_id: Optional[str] = None,
    ) -> PublishingPackage:
        """Creates a new PublishingPackage in DRAFT status."""
        story_res = await db.execute(
            select(Story).where(Story.id == story_id, Story.tenant_id == tenant_id)
        )
        if not story_res.scalar_one_or_none():
            raise PublishingWorkflowError(f"Story '{story_id}' not found in tenant '{tenant_id}'.")

        version_res = await db.execute(
            select(StoryVersion).where(
                StoryVersion.id == story_version_id,
                StoryVersion.story_id == story_id,
            )
        )
        if not version_res.scalar_one_or_none():
            raise PublishingWorkflowError(
                f"StoryVersion '{story_version_id}' not found for story '{story_id}'."
            )

        package = PublishingPackage(
            tenant_id=tenant_id,
            story_id=story_id,
            story_version_id=story_version_id,
            primary_media_asset_id=primary_media_asset_id,
            primary_derivative_id=primary_derivative_id,
            visual_asset_id=visual_asset_id,
            subtitle_track_id=subtitle_track_id,
            canonical_title=canonical_title,
            canonical_description=canonical_description,
            canonical_caption=canonical_caption,
            tags=tags or [],
            status="DRAFT",
            created_by_user_id=creator_id,
        )
        db.add(package)
        await db.flush()
        return package

    @staticmethod
    async def add_or_update_platform_payload(
        db: AsyncSession,
        *,
        package_id: str,
        tenant_id: str,
        destination_type: str,
        account_id: str,
        adapted_title: str,
        adapted_description: str,
        adapted_caption: str = "",
        target_aspect_ratio: str = "16:9",
        selected_derivative_id: Optional[str] = None,
        selected_thumbnail_id: Optional[str] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> PlatformPayload:
        """Adds or updates a platform payload, automatically invalidating any prior approval."""
        pkg_res = await db.execute(
            select(PublishingPackage).where(
                PublishingPackage.id == package_id,
                PublishingPackage.tenant_id == tenant_id,
                PublishingPackage.is_deleted.is_(False),
            )
        )
        package = pkg_res.scalar_one_or_none()
        if not package:
            raise PublishingWorkflowError(f"PublishingPackage '{package_id}' not found.")

        if package.status in ("PUBLISHING", "PUBLISHED"):
            raise PublishingWorkflowError(f"Cannot mutate package in status '{package.status}'.")

        payload_res = await db.execute(
            select(PlatformPayload).where(
                PlatformPayload.package_id == package_id,
                PlatformPayload.destination_type == destination_type,
                PlatformPayload.account_id == account_id,
                PlatformPayload.tenant_id == tenant_id,
            )
        )
        payload = payload_res.scalar_one_or_none()

        if not payload:
            payload = PlatformPayload(
                tenant_id=tenant_id,
                package_id=package_id,
                destination_type=destination_type,
                account_id=account_id,
                adapted_title=adapted_title,
                adapted_description=adapted_description,
                adapted_caption=adapted_caption,
                target_aspect_ratio=target_aspect_ratio,
                selected_derivative_id=selected_derivative_id,
                selected_thumbnail_id=selected_thumbnail_id,
                custom_metadata=custom_metadata or {},
                validation_status="PENDING",
            )
            db.add(payload)
        else:
            payload.adapted_title = adapted_title
            payload.adapted_description = adapted_description
            payload.adapted_caption = adapted_caption
            payload.target_aspect_ratio = target_aspect_ratio
            payload.selected_derivative_id = selected_derivative_id
            payload.selected_thumbnail_id = selected_thumbnail_id
            payload.custom_metadata = custom_metadata or {}
            payload.validation_status = "PENDING"

        await db.flush()

        # Approval Invalidation: If package was approved or scheduled, reset to DRAFT
        if package.status in ("APPROVED", "SCHEDULED"):
            package.status = "DRAFT"
            package.current_approval_id = None
            # Append invalidation event to ledger
            inval_event = PublishingApprovalEvent(
                tenant_id=tenant_id,
                package_id=package.id,
                event_type="INVALIDATED",
                decided_by_user_id=package.created_by_user_id,
                decided_at=utc_now(),
                publication_manifest_hash="INVALIDATED",
                manifest_snapshot={},
                reason="Payload modified post-approval; approval invalidated.",
            )
            db.add(inval_event)

        await db.flush()
        return payload

    @staticmethod
    async def get_canonical_manifest_and_hash(
        db: AsyncSession,
        package: PublishingPackage,
    ) -> tuple[dict, str]:
        """Computes live canonical manifest and hash for the package and its attached payloads."""
        payloads_res = await db.execute(
            select(PlatformPayload).where(
                PlatformPayload.package_id == package.id,
                PlatformPayload.tenant_id == package.tenant_id,
            )
        )
        payloads = payloads_res.scalars().all()

        p_list = []
        for p in payloads:
            p_list.append(
                {
                    "destination_type": p.destination_type,
                    "account_id": p.account_id,
                    "adapted_title": p.adapted_title,
                    "adapted_description": p.adapted_description,
                    "adapted_caption": p.adapted_caption,
                    "target_aspect_ratio": p.target_aspect_ratio,
                    "selected_derivative_id": p.selected_derivative_id,
                    "selected_thumbnail_id": p.selected_thumbnail_id,
                    "custom_metadata": p.custom_metadata,
                }
            )

        # Fetch attached media assets
        media_ids = set()
        if package.primary_media_asset_id:
            media_ids.add(package.primary_media_asset_id)
        if package.visual_asset_id:
            media_ids.add(package.visual_asset_id)

        media_list = []
        if media_ids:
            m_res = await db.execute(
                select(MediaAsset).where(
                    MediaAsset.id.in_(list(media_ids)),
                    MediaAsset.tenant_id == package.tenant_id,
                )
            )
            assets = m_res.scalars().all()
            for a in assets:
                aspect = f"{a.width}:{a.height}" if a.width and a.height else "16:9"
                media_list.append(
                    {
                        "asset_id": a.id,
                        "asset_type": a.media_type,
                        "checksum_sha256": a.checksum,
                        "storage_path": a.storage_key,
                        "duration_seconds": a.duration or 0.0,
                        "aspect_ratio": aspect,
                    }
                )

        return build_publication_manifest(
            tenant_id=package.tenant_id,
            story_id=package.story_id,
            story_version_id=package.story_version_id,
            canonical_title=package.canonical_title,
            canonical_description=package.canonical_description,
            canonical_caption=package.canonical_caption,
            tags=package.tags,
            media_assets=media_list,
            platform_payloads=p_list,
        )

    @staticmethod
    async def approve_package(
        db: AsyncSession,
        *,
        package_id: str,
        tenant_id: str,
        approver_id: str,
        notes: Optional[str] = None,
    ) -> PublishingApprovalEvent:
        """Appends an immutable human approval event to the ledger."""
        pkg_res = await db.execute(
            select(PublishingPackage).where(
                PublishingPackage.id == package_id,
                PublishingPackage.tenant_id == tenant_id,
                PublishingPackage.is_deleted.is_(False),
            )
        )
        package = pkg_res.scalar_one_or_none()
        if not package:
            raise PublishingWorkflowError(f"PublishingPackage '{package_id}' not found.")

        if package.status not in ("DRAFT", "REJECTED", "VALIDATING"):
            raise PublishingWorkflowError(f"Cannot approve package in status '{package.status}'.")

        manifest, manifest_hash = await PublishingPackageService.get_canonical_manifest_and_hash(
            db, package
        )

        approval_event = PublishingApprovalEvent(
            tenant_id=tenant_id,
            package_id=package.id,
            event_type="APPROVED",
            decided_by_user_id=approver_id,
            decided_at=utc_now(),
            publication_manifest_hash=manifest_hash,
            manifest_snapshot=manifest,
            reason=notes,
        )
        db.add(approval_event)
        await db.flush()

        package.status = "APPROVED"
        package.current_approval_id = approval_event.id
        await db.flush()
        return approval_event

    @staticmethod
    async def reject_package(
        db: AsyncSession,
        *,
        package_id: str,
        tenant_id: str,
        approver_id: str,
        rejection_reason: str,
    ) -> PublishingApprovalEvent:
        """Appends an immutable human rejection event to the ledger."""
        if not rejection_reason or not rejection_reason.strip():
            raise PublishingWorkflowError(
                "Rejection reason is mandatory and must not be empty when rejecting a package."
            )

        pkg_res = await db.execute(
            select(PublishingPackage).where(
                PublishingPackage.id == package_id,
                PublishingPackage.tenant_id == tenant_id,
                PublishingPackage.is_deleted.is_(False),
            )
        )
        package = pkg_res.scalar_one_or_none()
        if not package:
            raise PublishingWorkflowError(f"PublishingPackage '{package_id}' not found.")

        manifest, manifest_hash = await PublishingPackageService.get_canonical_manifest_and_hash(
            db, package
        )

        approval_event = PublishingApprovalEvent(
            tenant_id=tenant_id,
            package_id=package.id,
            event_type="REJECTED",
            decided_by_user_id=approver_id,
            decided_at=utc_now(),
            publication_manifest_hash=manifest_hash,
            manifest_snapshot=manifest,
            reason=rejection_reason,
        )
        db.add(approval_event)
        await db.flush()

        package.status = "REJECTED"
        package.current_approval_id = None
        await db.flush()
        return approval_event

    @staticmethod
    async def reverify_manifest_at_dispatch(
        db: AsyncSession,
        package: PublishingPackage,
    ) -> bool:
        """Pre-flight dispatch-time re-verification.

        Checks:
        1. Package has an active approval.
        2. Recomputed live manifest hash strictly matches `approved.publication_manifest_hash`.

        Raises:
            ManifestTamperedError: If any discrepancy is detected.
        """
        if not package.current_approval_id:
            raise ManifestTamperedError("Package has no active human approval event.")

        approval_res = await db.execute(
            select(PublishingApprovalEvent).where(
                PublishingApprovalEvent.id == package.current_approval_id,
                PublishingApprovalEvent.tenant_id == package.tenant_id,
            )
        )
        approval_event = approval_res.scalar_one_or_none()
        if not approval_event or approval_event.event_type != "APPROVED":
            raise ManifestTamperedError("Package does not have a valid APPROVED approval record.")

        _, live_hash = await PublishingPackageService.get_canonical_manifest_and_hash(db, package)

        if live_hash != approval_event.publication_manifest_hash:
            raise ManifestTamperedError(
                f"Dispatch preflight failed: live content hash ({live_hash}) differs "
                f"from approved hash ({approval_event.publication_manifest_hash})."
            )

        return True
