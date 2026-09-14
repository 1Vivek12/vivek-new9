"""Celery and asynchronous background tasks for publishing dispatch and polling.

Implements:
1. execute_publish_pipeline: Pre-flight re-verification, sequential attempt logging,
   idempotent execution, and published item recording.
2. publish_package_task: Background Celery wrapper.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.base import utc_now
from app.db.models.media import MediaAsset
from app.db.models.publishing import (
    ConnectedAccount,
    PlatformPayload,
    PublishedItem,
    PublishingAttempt,
    PublishingJob,
    PublishingPackage,
)
from app.db.session import async_session_factory
from app.services.publishing.package_builder import ManifestTamperedError, PublishingPackageService
from app.services.publishing.providers.registry import provider_registry
from app.services.publishing.vault import get_credential_vault
from app.worker.celery_app import celery_app


async def execute_publish_pipeline(
    tenant_id: str,
    package_id: str,
    job_id: str,
    *,
    db_session: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """Core execution engine for publishing a package across all configured platform payloads."""
    vault = get_credential_vault()

    async def _run(db: AsyncSession) -> Dict[str, Any]:
        # 1. Fetch Job and Package
        job_res = await db.execute(
            select(PublishingJob).where(
                PublishingJob.id == job_id,
                PublishingJob.tenant_id == tenant_id,
            )
        )
        job = job_res.scalar_one_or_none()
        if not job:
            raise ValueError(f"PublishingJob '{job_id}' not found.")

        pkg_res = await db.execute(
            select(PublishingPackage).where(
                PublishingPackage.id == package_id,
                PublishingPackage.tenant_id == tenant_id,
                PublishingPackage.is_deleted.is_(False),
            )
        )
        package = pkg_res.scalar_one_or_none()
        if not package:
            job.job_status = "FAILED"
            job.safe_error_message = f"PublishingPackage '{package_id}' not found."
            await db.commit()
            return {"status": "FAILED", "error": job.safe_error_message}

        job.job_status = "RUNNING"
        job.started_at = utc_now()
        package.status = "PUBLISHING"
        await db.commit()

        # 2. Dispatch-Time Pre-Flight Re-verification
        try:
            await PublishingPackageService.reverify_manifest_at_dispatch(db, package)
        except ManifestTamperedError as exc:
            job.job_status = "FAILED"
            job.completed_at = utc_now()
            job.safe_error_message = f"Manifest pre-flight re-verification failed: {str(exc)}"
            package.status = "FAILED"
            await db.commit()
            return {"status": "FAILED", "error": job.safe_error_message}

        # 3. Fetch Platform Payloads
        payloads_res = await db.execute(
            select(PlatformPayload).where(
                PlatformPayload.package_id == package_id,
                PlatformPayload.tenant_id == tenant_id,
            )
        )
        payloads = payloads_res.scalars().all()

        if not payloads:
            job.job_status = "FAILED"
            job.completed_at = utc_now()
            job.safe_error_message = "No platform payloads found for publishing package."
            package.status = "FAILED"
            await db.commit()
            return {"status": "FAILED", "error": job.safe_error_message}

        all_success = True
        failed_count = 0
        published_results = []

        for payload in payloads:
            start_mono = time.monotonic()
            # Check connected account
            acc_res = await db.execute(
                select(ConnectedAccount).where(
                    ConnectedAccount.id == payload.account_id,
                    ConnectedAccount.tenant_id == tenant_id,
                    ConnectedAccount.is_deleted.is_(False),
                )
            )
            account = acc_res.scalar_one_or_none()

            # Sequential attempt tracking
            prev_attempts_res = await db.execute(
                select(PublishingAttempt).where(PublishingAttempt.job_id == job_id)
            )
            attempt_num = len(prev_attempts_res.scalars().all()) + 1

            attempt = PublishingAttempt(
                tenant_id=tenant_id,
                job_id=job_id,
                attempt_number=attempt_num,
                started_at=utc_now(),
                outcome="UNKNOWN",
            )
            db.add(attempt)
            job.attempts += 1
            await db.commit()

            if not account or account.connection_status != "CONNECTED":
                attempt.outcome = "PERMANENT_FAILURE"
                attempt.platform_error_code = "ACCOUNT_INACTIVE"
                attempt.sanitized_error_message = (
                    "Connected account is disconnected, expired, or missing."
                )
                attempt.duration_ms = int((time.monotonic() - start_mono) * 1000)
                failed_count += 1
                all_success = False
                await db.commit()
                continue

            # Fetch media assets
            media_list = []
            media_ids = []
            if package.primary_media_asset_id:
                media_ids.append(package.primary_media_asset_id)
            if package.visual_asset_id:
                media_ids.append(package.visual_asset_id)

            if media_ids:
                m_res = await db.execute(
                    select(MediaAsset).where(
                        MediaAsset.id.in_(media_ids),
                        MediaAsset.tenant_id == tenant_id,
                    )
                )
                assets = m_res.scalars().all()
                for a in assets:
                    aspect = f"{a.width}:{a.height}" if a.width and a.height else "16:9"
                    media_list.append(
                        {
                            "asset_id": a.id,
                            "storage_path": a.storage_key,
                            "rights_metadata": a.rights_metadata,
                            "duration_seconds": a.duration or 0.0,
                            "aspect_ratio": aspect,
                        }
                    )

            # Call provider
            try:
                provider = provider_registry.get_provider(payload.destination_type)
                result = await provider.publish(
                    db=db,
                    payload=payload,
                    account=account,
                    vault=vault,
                    media_assets=media_list,
                )

                attempt.duration_ms = int((time.monotonic() - start_mono) * 1000)

                if result.success and result.external_id:
                    attempt.outcome = "SUCCESS"
                    attempt.http_status_code = 200

                    # Record PublishedItem strictly with verified external ID
                    published_item = PublishedItem(
                        tenant_id=tenant_id,
                        package_id=package_id,
                        account_id=account.id,
                        destination_type=payload.destination_type,
                        external_item_id=result.external_id,
                        external_url=result.url,
                        published_at=utc_now(),
                        visibility="PUBLIC",
                        platform_state="ACTIVE",
                    )
                    db.add(published_item)
                    published_results.append(
                        {
                            "destination_type": payload.destination_type,
                            "external_id": result.external_id,
                            "url": published_item.external_url,
                        }
                    )
                else:
                    attempt.outcome = "PERMANENT_FAILURE"
                    attempt.sanitized_error_message = (
                        result.error_message
                        if not result.success
                        else "Provider reported success but returned no external item ID."
                    )
                    all_success = False
                    failed_count += 1
            except Exception as exc:
                attempt.outcome = "TEMPORARY_FAILURE"
                attempt.sanitized_error_message = str(exc)
                attempt.duration_ms = int((time.monotonic() - start_mono) * 1000)
                all_success = False
                failed_count += 1

            await db.commit()

        # Update final job and package state
        job.completed_at = utc_now()
        if all_success:
            job.job_status = "SUCCESS"
            package.status = "PUBLISHED"
        elif failed_count == len(payloads):
            job.job_status = "FAILED"
            package.status = "FAILED"
        else:
            job.job_status = "PARTIALLY_PUBLISHED"
            package.status = "PARTIALLY_PUBLISHED"

        await db.commit()
        return {
            "status": job.job_status,
            "published_results": published_results,
            "failed_count": failed_count,
        }

    if db_session is not None:
        return await _run(db_session)
    else:
        async with async_session_factory() as session:
            return await _run(session)


@celery_app.task(name="tasks.publish_package")
def publish_package_task(tenant_id: str, package_id: str, job_id: str) -> Dict[str, Any]:
    """Celery background wrapper for publish package execution."""
    logger.info(
        f"Publish package task invoked for tenant {tenant_id}, package {package_id}, job {job_id}"
    )
    return asyncio.run(
        execute_publish_pipeline(tenant_id=tenant_id, package_id=package_id, job_id=job_id)
    )
