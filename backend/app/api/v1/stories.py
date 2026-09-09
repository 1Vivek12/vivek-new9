"""Stories and Editorial Core API endpoints."""

import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import check_permission
from app.core.tenant import TenantContext, get_tenant_context
from app.db.base import utc_now
from app.db.models.audit import AuditLog
from app.db.models.category import Category
from app.db.models.source import StorySource
from app.db.models.story import Story
from app.db.models.version import StoryVersion
from app.db.session import get_db_session
from app.schemas.source import SourceCreate, SourceResponse
from app.schemas.story import (
    StoryCreate,
    StoryDetailResponse,
    StoryResponse,
    StoryStatusTransitionRequest,
    StoryUpdate,
)
from app.schemas.version import VersionCreate, VersionResponse
from app.services.editorial.lifecycle import (
    EditorialState,
    validate_transition,
)
from app.services.publishing.base import (
    ContentState,
    MockPublishingBoundary,
    PublishingPayload,
)

router = APIRouter(prefix="/stories", tags=["Editorial Stories"])


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text)


# -----------------------------------------------------------------------------
# Story CRUD
# -----------------------------------------------------------------------------


@router.get("", response_model=List[StoryResponse])
async def list_stories(
    category_id: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[StoryResponse]:
    """List stories strictly scoped to caller's authorized tenant."""
    check_permission(context, "VIEW_EDITORIAL")
    stmt = (
        select(Story)
        .where(Story.tenant_id == context.tenant_id)
        .order_by(desc(Story.created_at))
        .offset(offset)
        .limit(limit)
    )
    if category_id:
        stmt = stmt.where(Story.category_id == category_id)
    if status_filter:
        stmt = stmt.where(Story.status == status_filter.upper())

    result = await db.execute(stmt)
    return [StoryResponse.model_validate(s) for s in result.scalars().all()]


@router.post("", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
async def create_story(
    payload: StoryCreate,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> StoryResponse:
    """Create a new story within caller's authorized tenant."""
    check_permission(context, "CREATE_STORY")

    slug = payload.slug or slugify(payload.title)

    # Verify category belongs to same tenant if provided
    if payload.category_id:
        cat_check = await db.execute(
            select(Category).where(
                Category.id == payload.category_id,
                Category.tenant_id == context.tenant_id,
            )
        )
        if not cat_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category '{payload.category_id}' does not exist in this tenant workspace",
            )

    # Check slug uniqueness in tenant
    existing = await db.execute(
        select(Story).where(Story.tenant_id == context.tenant_id, Story.slug == slug)
    )
    if existing.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    story = Story(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        title=payload.title,
        slug=slug,
        summary=payload.summary,
        category_id=payload.category_id,
        assignment_id=payload.assignment_id,
        priority=payload.priority.upper(),
        status=EditorialState.IDEA.value,
        created_by_user_id=context.user_id,
    )
    db.add(story)

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="STORY_CREATED",
        resource_type="story",
        resource_id=story.id,
        metadata_payload={"title": story.title, "slug": story.slug},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(story)
    return StoryResponse.model_validate(story)


@router.get("/{story_id}", response_model=StoryDetailResponse)
async def get_story_detail(
    story_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> StoryDetailResponse:
    """Fetch complete story details, enforcing tenant boundary (IDOR protection)."""
    check_permission(context, "VIEW_EDITORIAL")
    stmt = (
        select(Story)
        .where(Story.id == story_id, Story.tenant_id == context.tenant_id)
        .options(
            selectinload(Story.category),
            selectinload(Story.assignment),
            selectinload(Story.sources),
            selectinload(Story.versions),
        )
    )
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()

    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story '{story_id}' not found in this workspace",
        )
    return StoryDetailResponse.model_validate(story)


@router.patch("/{story_id}", response_model=StoryResponse)
async def update_story(
    story_id: str,
    payload: StoryUpdate,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> StoryResponse:
    """Update story metadata, strictly enforcing tenant boundary."""
    check_permission(context, "EDIT_STORY")
    stmt = select(Story).where(
        Story.id == story_id,
        Story.tenant_id == context.tenant_id,
    )
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()

    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story '{story_id}' not found in this workspace",
        )

    if payload.title is not None:
        story.title = payload.title
    if payload.summary is not None:
        story.summary = payload.summary
    if payload.category_id is not None:
        story.category_id = payload.category_id
    if payload.assignment_id is not None:
        story.assignment_id = payload.assignment_id
    if payload.priority is not None:
        story.priority = payload.priority.upper()
    if payload.editorial_owner_id is not None:
        story.editorial_owner_id = payload.editorial_owner_id

    story.updated_by_user_id = context.user_id

    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="STORY_UPDATED",
        resource_type="story",
        resource_id=story.id,
        metadata_payload={"updated_fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(story)
    return StoryResponse.model_validate(story)


# -----------------------------------------------------------------------------
# Story Editorial Lifecycle & Approval Transition
# -----------------------------------------------------------------------------


@router.post("/{story_id}/status", response_model=StoryResponse)
async def transition_story_status(
    story_id: str,
    payload: StoryStatusTransitionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> StoryResponse:
    """Execute deterministic lifecycle transition with human approval gating."""
    stmt = select(Story).where(
        Story.id == story_id,
        Story.tenant_id == context.tenant_id,
    )
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()

    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story '{story_id}' not found in this workspace",
        )

    # Validate transition against state machine and role permissions
    next_state = validate_transition(
        current_state_str=story.status,
        requested_state_str=payload.target_status,
        context=context,
        rejection_reason=payload.rejection_reason,
    )

    old_status = story.status
    story.status = next_state.value
    story.updated_by_user_id = context.user_id

    # Handle Human Approval
    if next_state == EditorialState.APPROVED:
        story.approved_by_user_id = context.user_id
        story.approved_at = utc_now()
        story.rejection_reason = None
    elif next_state == EditorialState.REJECTED:
        story.rejection_reason = payload.rejection_reason
    elif next_state == EditorialState.PUBLISHED:
        # Connect to Phase 1 Publishing Guard
        publishing_guard = MockPublishingBoundary()
        publishing_payload = PublishingPayload(
            content_id=story.id,
            tenant_id=story.tenant_id,
            title=story.title,
            body=story.summary or "",
            state=ContentState.APPROVED,  # must have passed approval
            approved_by_user_id=story.approved_by_user_id,
            approval_timestamp=story.approved_at.timestamp() if story.approved_at else None,
        )
        await publishing_guard.publish(publishing_payload)

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="STORY_STATUS_CHANGED",
        resource_type="story",
        resource_id=story.id,
        metadata_payload={
            "from_status": old_status,
            "to_status": story.status,
            "approved_by": story.approved_by_user_id,
            "rejection_reason": story.rejection_reason,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(story)
    return StoryResponse.model_validate(story)


# -----------------------------------------------------------------------------
# Story Sources / References
# -----------------------------------------------------------------------------


@router.get("/{story_id}/sources", response_model=List[SourceResponse])
async def list_story_sources(
    story_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[SourceResponse]:
    """List sources attached to story, enforcing tenant boundary."""
    check_permission(context, "VIEW_EDITORIAL")

    # Verify story exists in caller's tenant
    story_res = await db.execute(
        select(Story).where(Story.id == story_id, Story.tenant_id == context.tenant_id)
    )
    if not story_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story '{story_id}' not found in this workspace",
        )

    stmt = (
        select(StorySource)
        .where(
            StorySource.story_id == story_id,
            StorySource.tenant_id == context.tenant_id,
        )
        .order_by(desc(StorySource.created_at))
    )
    result = await db.execute(stmt)
    return [SourceResponse.model_validate(s) for s in result.scalars().all()]


@router.post(
    "/{story_id}/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_story_source(
    story_id: str,
    payload: SourceCreate,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> SourceResponse:
    """Attach source/reference metadata to story within tenant boundary."""
    check_permission(context, "ADD_SOURCE")

    story_res = await db.execute(
        select(Story).where(Story.id == story_id, Story.tenant_id == context.tenant_id)
    )
    story = story_res.scalar_one_or_none()
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story '{story_id}' not found in this workspace",
        )

    source = StorySource(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        story_id=story.id,
        title=payload.title,
        url=payload.url,
        publisher_name=payload.publisher_name,
        source_type=payload.source_type.upper(),
        published_at=payload.published_at,
        accessed_at=utc_now(),
        reliability_score=payload.reliability_score,
        rights_metadata=payload.rights_metadata,
        notes=payload.notes,
        created_by_user_id=context.user_id,
    )
    db.add(source)

    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="SOURCE_ADDED",
        resource_type="story",
        resource_id=story.id,
        metadata_payload={"source_id": source.id, "title": source.title},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(source)
    return SourceResponse.model_validate(source)


# -----------------------------------------------------------------------------
# Story Versions (Immutable)
# -----------------------------------------------------------------------------


@router.get("/{story_id}/versions", response_model=List[VersionResponse])
async def list_story_versions(
    story_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[VersionResponse]:
    """List immutable draft versions of a story, strictly enforcing tenant boundary."""
    check_permission(context, "VIEW_EDITORIAL")

    story_res = await db.execute(
        select(Story).where(Story.id == story_id, Story.tenant_id == context.tenant_id)
    )
    if not story_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story '{story_id}' not found in this workspace",
        )

    stmt = (
        select(StoryVersion)
        .where(
            StoryVersion.story_id == story_id,
            StoryVersion.tenant_id == context.tenant_id,
        )
        .order_by(desc(StoryVersion.version_number))
    )
    result = await db.execute(stmt)
    return [VersionResponse.model_validate(v) for v in result.scalars().all()]


@router.post(
    "/{story_id}/versions",
    response_model=VersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_story_version(
    story_id: str,
    payload: VersionCreate,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> VersionResponse:
    """Create a new immutable version snapshot for a story."""
    check_permission(context, "CREATE_VERSION")

    story_res = await db.execute(
        select(Story).where(Story.id == story_id, Story.tenant_id == context.tenant_id)
    )
    story = story_res.scalar_one_or_none()
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story '{story_id}' not found in this workspace",
        )

    # Compute next version number
    max_ver_res = await db.execute(
        select(func.coalesce(func.max(StoryVersion.version_number), 0)).where(
            StoryVersion.story_id == story_id,
            StoryVersion.tenant_id == context.tenant_id,
        )
    )
    next_version_num = (max_ver_res.scalar_one() or 0) + 1

    version = StoryVersion(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        story_id=story.id,
        version_number=next_version_num,
        headline=payload.headline,
        body_payload=payload.body_payload,
        body_text=payload.body_text,
        change_summary=payload.change_summary,
        created_by_user_id=context.user_id,
        created_at=utc_now(),
    )
    db.add(version)

    # Update story title/updated_at
    story.title = payload.headline
    story.updated_by_user_id = context.user_id

    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="STORY_VERSION_CREATED",
        resource_type="story",
        resource_id=story.id,
        metadata_payload={
            "version_number": next_version_num,
            "change_summary": payload.change_summary,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(version)
    return VersionResponse.model_validate(version)
