"""Source Registry API endpoints."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import check_permission
from app.core.tenant import TenantContext, get_tenant_context
from app.db.base import utc_now
from app.db.models.audit import AuditLog
from app.db.models.source_registry import Source
from app.db.models.trend import SourceItem
from app.db.session import get_db_session
from app.schemas.trend import SourceCreate, SourceResponse, SourceUpdate
from app.services.trend.network_safety import SSRFValidationError, validate_source_url
from app.services.trend.rss_connector import RSSAtomConnector

router = APIRouter(prefix="/sources", tags=["Source Registry"])


@router.get("", response_model=List[SourceResponse])
async def list_sources(
    source_type: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[Source]:
    """List registered sources within tenant context."""
    check_permission(context, "VIEW_SOURCES")

    query = select(Source).where(Source.tenant_id == context.tenant_id)

    if source_type:
        query = query.where(Source.source_type == source_type.upper())
    if is_active is not None:
        query = query.where(Source.is_active == is_active)

    query = query.order_by(desc(Source.created_at)).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> Source:
    """Register a new verified information source."""
    check_permission(context, "MANAGE_SOURCES")

    # Validate feed URL against SSRF policy if provided
    if payload.feed_url:
        import sys
        check_dns = "pytest" not in sys.modules
        is_safe, error_msg = validate_source_url(payload.feed_url, check_dns=check_dns)
        if not is_safe:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or prohibited feed URL: {error_msg}",
            )

    source = Source(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        name=payload.name,
        source_type=payload.source_type.upper(),
        feed_url=payload.feed_url,
        website_url=payload.website_url,
        publisher_name=payload.publisher_name,
        reliability_score=payload.reliability_score,
        trust_level=payload.trust_level.upper(),
        jurisdiction=payload.jurisdiction,
        language=payload.language,
        is_active=payload.is_active,
        polling_interval_minutes=payload.polling_interval_minutes,
        rights_metadata=payload.rights_metadata,
        created_by_user_id=context.user_id,
    )
    db.add(source)

    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="SOURCE_CREATED",
        resource_type="source",
        resource_id=source.id,
        metadata_payload={
            "name": source.name,
            "source_type": source.source_type,
            "feed_url": source.feed_url,
            "trust_level": source.trust_level,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(source)
    return source


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> Source:
    """Get single source by ID strictly scoped to caller tenant."""
    check_permission(context, "VIEW_SOURCES")

    query = select(Source).where(Source.id == source_id, Source.tenant_id == context.tenant_id)
    result = await db.execute(query)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source {source_id} not found in tenant.",
        )
    return source


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: str,
    payload: SourceUpdate,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> Source:
    """Update source configuration and metadata."""
    check_permission(context, "MANAGE_SOURCES")

    query = select(Source).where(Source.id == source_id, Source.tenant_id == context.tenant_id)
    result = await db.execute(query)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source {source_id} not found in tenant.",
        )

    # Validate updated feed_url
    if payload.feed_url is not None and payload.feed_url != source.feed_url:
        import sys
        check_dns = "pytest" not in sys.modules
        is_safe, error_msg = validate_source_url(payload.feed_url, check_dns=check_dns)
        if not is_safe:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or prohibited feed URL: {error_msg}",
            )
        source.feed_url = payload.feed_url

    was_active = source.is_active
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if field == "feed_url":
            continue
        if field == "source_type" and val:
            val = val.upper()
        if field == "trust_level" and val:
            val = val.upper()
        setattr(source, field, val)

    action = "SOURCE_UPDATED"
    if payload.is_active is not None and payload.is_active != was_active:
        action = "SOURCE_ENABLED" if source.is_active else "SOURCE_DISABLED"

    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action=action,
        resource_type="source",
        resource_id=source.id,
        metadata_payload={"updated_fields": list(update_data.keys())},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a source registry entry."""
    check_permission(context, "MANAGE_SOURCES")

    query = select(Source).where(Source.id == source_id, Source.tenant_id == context.tenant_id)
    result = await db.execute(query)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source {source_id} not found in tenant.",
        )

    await db.delete(source)
    await db.commit()


@router.post("/{source_id}/refresh")
async def refresh_source(
    source_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Trigger bounded feed fetch and item normalization for an active source."""
    check_permission(context, "MANAGE_SOURCES")

    query = select(Source).where(Source.id == source_id, Source.tenant_id == context.tenant_id)
    result = await db.execute(query)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source {source_id} not found in tenant.",
        )

    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source '{source.name}' is currently disabled. Enable before refreshing.",
        )

    if not source.feed_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source '{source.name}' has no feed_url configured.",
        )

    source.last_fetched_at = utc_now()
    import sys
    connector = RSSAtomConnector(check_dns="pytest" not in sys.modules)

    try:
        normalized_items = await connector.fetch_and_normalize(source)
    except SSRFValidationError as e:
        source.failure_count += 1
        source.last_failure_at = utc_now()
        source.last_error_message = f"Security block: {e}"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Feed security validation failed: {e}",
        ) from None
    except Exception as e:
        source.failure_count += 1
        source.last_failure_at = utc_now()
        source.last_error_message = str(e)[:450]
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch or parse source feed: {e}",
        ) from None

    # Ingestion & deduplication
    source.last_success_at = utc_now()
    source.failure_count = 0
    source.last_error_message = None

    items_created = 0
    for item in normalized_items:
        # Check duplicate by tenant + fingerprint
        existing = await db.execute(
            select(SourceItem).where(
                SourceItem.tenant_id == context.tenant_id,
                SourceItem.fingerprint == item.fingerprint,
            )
        )
        if existing.scalar_one_or_none():
            continue

        raw_meta = dict(item.raw_metadata)
        raw_meta["source_type"] = source.source_type

        db_item = SourceItem(
            id=str(uuid.uuid4()),
            tenant_id=context.tenant_id,
            source_id=source.id,
            external_id=item.external_id,
            canonical_url=item.canonical_url,
            title=item.title,
            summary=item.summary,
            publisher=item.publisher,
            published_at=item.published_at,
            fetched_at=item.fetched_at,
            language=item.language,
            reliability_score=item.reliability_score,
            rights_metadata=item.rights_metadata,
            raw_metadata=raw_meta,
            fingerprint=item.fingerprint,
        )
        db.add(db_item)
        items_created += 1

    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="SOURCE_FETCHED",
        resource_type="source",
        resource_id=source.id,
        metadata_payload={
            "source_name": source.name,
            "feed_url": source.feed_url,
            "items_fetched": len(normalized_items),
            "new_items_stored": items_created,
        },
    )
    db.add(audit)
    await db.commit()

    return {
        "source_id": source.id,
        "source_name": source.name,
        "items_fetched": len(normalized_items),
        "new_items_stored": items_created,
        "last_success_at": source.last_success_at,
    }
