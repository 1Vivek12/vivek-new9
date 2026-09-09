"""Content Opportunities and Editorial Story Conversion API endpoints."""

import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import check_permission
from app.core.tenant import TenantContext, get_tenant_context
from app.db.base import utc_now
from app.db.models.audit import AuditLog
from app.db.models.source import StorySource
from app.db.models.story import Story
from app.db.models.trend import ContentOpportunity, SourceItem
from app.db.session import get_db_session
from app.schemas.story import StoryResponse
from app.schemas.trend import (
    OpportunityConvertRequest,
    OpportunityResponse,
    SourceItemResponse,
)

router = APIRouter(prefix="/opportunities", tags=["Content Opportunities"])


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    slug = re.sub(r"[-\s]+", "-", text)
    return slug[:180] or "story"


@router.get("", response_model=List[OpportunityResponse])
async def list_opportunities(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    urgency: Optional[str] = Query(default=None),
    min_score: Optional[float] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[ContentOpportunity]:
    """List editorial content opportunities within tenant context."""
    check_permission(context, "VIEW_TRENDS")

    query = select(ContentOpportunity).where(ContentOpportunity.tenant_id == context.tenant_id)

    if status_filter:
        query = query.where(ContentOpportunity.status == status_filter.upper())
    if urgency:
        query = query.where(ContentOpportunity.urgency == urgency.upper())
    if min_score is not None:
        query = query.where(ContentOpportunity.trend_score >= min_score)

    query = query.order_by(
        desc(ContentOpportunity.trend_score), desc(ContentOpportunity.created_at)
    )
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
async def get_opportunity(
    opportunity_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> OpportunityResponse:
    """Get single content opportunity and its associated source items."""
    check_permission(context, "VIEW_TRENDS")

    query = select(ContentOpportunity).where(
        ContentOpportunity.id == opportunity_id,
        ContentOpportunity.tenant_id == context.tenant_id,
    )
    result = await db.execute(query)
    opp = result.scalar_one_or_none()

    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content opportunity {opportunity_id} not found in tenant.",
        )

    response = OpportunityResponse.model_validate(opp)

    # Load related source items if linked to a group
    if opp.similar_story_group_id:
        items_query = (
            select(SourceItem)
            .where(
                SourceItem.similar_story_group_id == opp.similar_story_group_id,
                SourceItem.tenant_id == context.tenant_id,
            )
            .order_by(desc(SourceItem.fetched_at))
        )
        items_res = await db.execute(items_query)
        response.related_items = [
            SourceItemResponse.model_validate(it) for it in items_res.scalars().all()
        ]

    return response


@router.post("/{opportunity_id}/accept", response_model=OpportunityResponse)
async def accept_opportunity(
    opportunity_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> ContentOpportunity:
    """Editor reviews and accepts a content opportunity."""
    check_permission(context, "MANAGE_OPPORTUNITIES")

    query = select(ContentOpportunity).where(
        ContentOpportunity.id == opportunity_id,
        ContentOpportunity.tenant_id == context.tenant_id,
    )
    result = await db.execute(query)
    opp = result.scalar_one_or_none()

    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content opportunity {opportunity_id} not found in tenant.",
        )

    if opp.status in ("CONVERTED_TO_STORY", "REJECTED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot accept opportunity in '{opp.status}' state.",
        )

    opp.status = "ACCEPTED"
    opp.actioned_by_user_id = context.user_id
    opp.actioned_at = utc_now()

    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="OPPORTUNITY_ACCEPTED",
        resource_type="content_opportunity",
        resource_id=opp.id,
        metadata_payload={"topic": opp.topic, "headline": opp.headline},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(opp)
    return opp


@router.post("/{opportunity_id}/reject", response_model=OpportunityResponse)
async def reject_opportunity(
    opportunity_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> ContentOpportunity:
    """Editor reviews and rejects a content opportunity."""
    check_permission(context, "MANAGE_OPPORTUNITIES")

    query = select(ContentOpportunity).where(
        ContentOpportunity.id == opportunity_id,
        ContentOpportunity.tenant_id == context.tenant_id,
    )
    result = await db.execute(query)
    opp = result.scalar_one_or_none()

    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content opportunity {opportunity_id} not found in tenant.",
        )

    if opp.status == "CONVERTED_TO_STORY":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reject opportunity that has already been converted to a story.",
        )

    opp.status = "REJECTED"
    opp.actioned_by_user_id = context.user_id
    opp.actioned_at = utc_now()

    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="OPPORTUNITY_REJECTED",
        resource_type="content_opportunity",
        resource_id=opp.id,
        metadata_payload={"topic": opp.topic, "headline": opp.headline},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(opp)
    return opp


@router.post(
    "/{opportunity_id}/convert-to-story",
    response_model=StoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def convert_opportunity_to_story(
    opportunity_id: str,
    payload: OpportunityConvertRequest = OpportunityConvertRequest(),
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> Story:
    """
    Manually convert an opportunity into a Phase 2 Story.
    Invariants:
    - Creates Story strictly in initial 'IDEA' state.
    - Preserves tenant ownership.
    - Preserves source citations as attached StorySource records.
    - Creates audit log OPPORTUNITY_CONVERTED_TO_STORY.
    - Does NOT auto-approve or auto-publish.
    """
    check_permission(context, "MANAGE_OPPORTUNITIES")
    check_permission(context, "CREATE_STORY")

    query = select(ContentOpportunity).where(
        ContentOpportunity.id == opportunity_id,
        ContentOpportunity.tenant_id == context.tenant_id,
    )
    result = await db.execute(query)
    opp = result.scalar_one_or_none()

    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content opportunity {opportunity_id} not found in tenant.",
        )

    if opp.status == "CONVERTED_TO_STORY":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Opportunity {opportunity_id} already converted to story "
                f"{opp.converted_story_id}."
            ),
        )

    # Generate unique slug in tenant
    base_slug = slugify(opp.headline)
    slug = base_slug
    existing_slug = await db.execute(
        select(Story).where(Story.tenant_id == context.tenant_id, Story.slug == slug)
    )
    if existing_slug.scalar_one_or_none():
        slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    # 1. Create Phase 2 Story in IDEA status
    story = Story(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        title=opp.headline,
        slug=slug,
        summary=opp.summary,
        category_id=payload.category_id or opp.category_id,
        priority=payload.priority.upper() if payload.priority else opp.urgency,
        status="IDEA",  # Mandatory initial state: NEVER auto-approved or published
        editorial_owner_id=payload.editorial_owner_id or context.user_id,
        created_by_user_id=context.user_id,
    )
    db.add(story)
    await db.flush()

    # 2. Attach source citations if linked to a group
    attached_sources_count = 0
    if opp.similar_story_group_id:
        items_query = select(SourceItem).where(
            SourceItem.similar_story_group_id == opp.similar_story_group_id,
            SourceItem.tenant_id == context.tenant_id,
        )
        items_res = await db.execute(items_query)
        group_items = list(items_res.scalars().all())

        for item in group_items:
            story_source = StorySource(
                id=str(uuid.uuid4()),
                tenant_id=context.tenant_id,
                story_id=story.id,
                title=item.title,
                url=item.canonical_url,
                publisher_name=item.publisher,
                source_type=item.raw_metadata.get("source_type", "OTHER"),
                published_at=item.published_at,
                accessed_at=utc_now(),
                reliability_score=item.reliability_score,
                rights_metadata=item.rights_metadata,
                notes=f"Converted from Trend Opportunity '{opp.topic}'",
                created_by_user_id=context.user_id,
            )
            db.add(story_source)
            attached_sources_count += 1

    # 3. Mark Opportunity as converted
    opp.status = "CONVERTED_TO_STORY"
    opp.converted_story_id = story.id
    opp.actioned_by_user_id = context.user_id
    opp.actioned_at = utc_now()

    # 4. Audit Log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="OPPORTUNITY_CONVERTED_TO_STORY",
        resource_type="content_opportunity",
        resource_id=opp.id,
        metadata_payload={
            "created_story_id": story.id,
            "story_slug": story.slug,
            "attached_sources_count": attached_sources_count,
            "initial_story_status": "IDEA",
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(story)
    return story
