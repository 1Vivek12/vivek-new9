"""Trend Radar and Topic Search API endpoints."""

import uuid
from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import check_permission
from app.core.tenant import TenantContext, get_tenant_context
from app.db.base import utc_now
from app.db.models.audit import AuditLog
from app.db.models.source_registry import Source
from app.db.models.trend import ContentOpportunity, SimilarStoryGroup, SourceItem
from app.db.session import get_db_session
from app.schemas.trend import (
    OpportunityResponse,
    SimilarStoryGroupDetailResponse,
    SimilarStoryGroupResponse,
    SourceItemResponse,
    TrendSearchRequest,
    TrendSearchResponse,
)
from app.services.trend.clustering import is_potentially_related, synthesize_group_opportunity

router = APIRouter(tags=["Trend Radar"])


@router.post("/trend/search", response_model=TrendSearchResponse)
async def search_topic_trends(
    payload: TrendSearchRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> TrendSearchResponse:
    """Search topic across tenant source items, cluster stories, and generate opportunities."""
    check_permission(context, "VIEW_TRENDS")

    now = utc_now()
    window_start = now - timedelta(hours=payload.time_window_hours)

    # 1. Query matching source items within tenant
    query = (
        select(SourceItem)
        .join(Source, SourceItem.source_id == Source.id)
        .where(
            SourceItem.tenant_id == context.tenant_id,
            or_(
                SourceItem.published_at >= window_start,
                SourceItem.fetched_at >= window_start,
            ),
        )
    )

    # Lexical matching on query tokens
    search_terms = payload.query.strip().split()
    for term in search_terms:
        term_pattern = f"%{term}%"
        query = query.where(
            or_(
                SourceItem.title.ilike(term_pattern),
                SourceItem.summary.ilike(term_pattern),
            )
        )

    if payload.language:
        query = query.where(SourceItem.language == payload.language)
    if payload.source_type:
        query = query.where(Source.source_type == payload.source_type.upper())
    if payload.min_reliability is not None:
        query = query.where(SourceItem.reliability_score >= payload.min_reliability)
    if payload.jurisdiction:
        query = query.where(Source.jurisdiction == payload.jurisdiction)

    query = query.order_by(desc(SourceItem.fetched_at)).limit(100)
    items_res = await db.execute(query)
    matching_items = list(items_res.scalars().all())

    # 2. Cluster items into similar story groups
    clusters: List[List[SourceItem]] = []
    for item in matching_items:
        assigned = False
        for cluster in clusters:
            # If related to representative/first item in cluster
            if is_potentially_related(
                item, cluster[0], time_window_hours=payload.time_window_hours
            ):
                cluster.append(item)
                assigned = True
                break
        if not assigned:
            clusters.append([item])

    groups_created: List[SimilarStoryGroup] = []
    opportunities_created: List[ContentOpportunity] = []

    for cluster in clusters:
        cluster_items = cluster
        rep_title = cluster_items[0].title
        now_utc = utc_now()

        # Check existing group by representative title in tenant
        existing_group_res = await db.execute(
            select(SimilarStoryGroup).where(
                SimilarStoryGroup.tenant_id == context.tenant_id,
                SimilarStoryGroup.representative_title == rep_title,
            )
        )
        group = existing_group_res.scalar_one_or_none()

        if not group:
            pub_count = len(set(it.publisher for it in cluster_items if it.publisher)) or 1
            rel_scores = [
                it.reliability_score for it in cluster_items if it.reliability_score is not None
            ]
            group = SimilarStoryGroup(
                id=str(uuid.uuid4()),
                tenant_id=context.tenant_id,
                representative_title=rep_title,
                topic_keywords=payload.query.split(),
                source_count=len(cluster_items),
                independent_publisher_count=pub_count,
                strongest_source_reliability=max(rel_scores, default=70.0),
                first_seen_at=min(
                    (it.published_at or it.fetched_at for it in cluster_items),
                    default=now_utc,
                ),
                latest_seen_at=max(
                    (it.published_at or it.fetched_at for it in cluster_items),
                    default=now_utc,
                ),
                trend_score=0.0,
            )
            db.add(group)
            await db.flush()

        # Assign items to group
        for ci in cluster_items:
            ci.similar_story_group_id = group.id

        # Generate Opportunity
        existing_opp_res = await db.execute(
            select(ContentOpportunity).where(
                ContentOpportunity.tenant_id == context.tenant_id,
                ContentOpportunity.similar_story_group_id == group.id,
            )
        )
        opportunity = existing_opp_res.scalar_one_or_none()

        if not opportunity:
            opportunity = synthesize_group_opportunity(
                group, cluster_items, topic=payload.query, now=now_utc
            )
            opportunity.id = str(uuid.uuid4())
            db.add(opportunity)
            await db.flush()
        else:
            # Update opportunity trend score
            refreshed_opp = synthesize_group_opportunity(
                group, cluster_items, topic=payload.query, now=now_utc
            )
            opportunity.trend_score = refreshed_opp.trend_score
            opportunity.confidence_score = refreshed_opp.confidence_score
            opportunity.urgency = refreshed_opp.urgency
            opportunity.score_explanation = refreshed_opp.score_explanation
            opportunity.source_count = refreshed_opp.source_count
            opportunity.publisher_count = refreshed_opp.publisher_count

        groups_created.append(group)
        opportunities_created.append(opportunity)

    audit = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        action="TREND_SEARCHED",
        resource_type="trend",
        resource_id=None,
        metadata_payload={
            "query": payload.query,
            "matching_items": len(matching_items),
            "clusters_found": len(clusters),
        },
    )
    db.add(audit)
    await db.commit()

    opp_responses = [
        OpportunityResponse.model_validate(opp) for opp in opportunities_created
    ]
    grp_responses = [
        SimilarStoryGroupResponse(
            id=grp.id,
            tenant_id=grp.tenant_id,
            representative_title=grp.representative_title,
            topic_keywords=grp.topic_keywords,
            source_count=grp.source_count,
            independent_publisher_count=grp.independent_publisher_count,
            strongest_source_reliability=grp.strongest_source_reliability,
            first_seen_at=grp.first_seen_at,
            latest_seen_at=grp.latest_seen_at,
            trend_score=grp.trend_score,
            created_at=grp.created_at,
            updated_at=grp.updated_at,
        )
        for grp in groups_created
    ]
    item_responses = [
        SourceItemResponse.model_validate(it) for it in matching_items
    ]

    return TrendSearchResponse(
        query=payload.query,
        total_matching_items=len(matching_items),
        opportunities=opp_responses,
        groups=grp_responses,
        items=item_responses,
    )


@router.get("/trends", response_model=List[SimilarStoryGroupResponse])
async def list_trends(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[SimilarStoryGroup]:
    """List grouped trend signals within tenant context ordered by trend score."""
    check_permission(context, "VIEW_TRENDS")

    query = (
        select(SimilarStoryGroup)
        .where(SimilarStoryGroup.tenant_id == context.tenant_id)
        .order_by(desc(SimilarStoryGroup.trend_score), desc(SimilarStoryGroup.latest_seen_at))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/trends/{trend_id}", response_model=SimilarStoryGroupDetailResponse)
async def get_trend_group(
    trend_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> SimilarStoryGroupDetailResponse:
    """Get single trend story group with its associated source items."""
    check_permission(context, "VIEW_TRENDS")

    query = (
        select(SimilarStoryGroup)
        .options(selectinload(SimilarStoryGroup.items))
        .where(
            SimilarStoryGroup.id == trend_id,
            SimilarStoryGroup.tenant_id == context.tenant_id,
        )
    )
    result = await db.execute(query)
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trend group {trend_id} not found in tenant.",
        )

    res = SimilarStoryGroupDetailResponse.model_validate(group)
    res.items = [SourceItemResponse.model_validate(i) for i in group.items]
    return res
