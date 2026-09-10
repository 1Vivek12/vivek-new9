"""API endpoints for Phase 4 AI Research jobs, evidence, claims, and briefs."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import check_permission
from app.core.tenant import TenantContext, get_tenant_context
from app.db.models.research import (
    ResearchBrief,
    ResearchClaim,
    ResearchEvidence,
    ResearchJob,
)
from app.db.models.story import Story
from app.db.session import get_db_session
from app.schemas.research import (
    ResearchBriefResponse,
    ResearchClaimResponse,
    ResearchEvidenceResponse,
    ResearchJobCreate,
    ResearchJobResponse,
)
from app.services.ai.research_engine import ResearchEngine

router = APIRouter(tags=["AI Research"])
engine = ResearchEngine()


@router.post(
    "/stories/{story_id}/research",
    response_model=ResearchJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_research_job(
    story_id: str,
    payload: Optional[ResearchJobCreate] = None,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> ResearchJobResponse:
    """Create and execute an AI research job for an editorial story."""
    check_permission(context, "TRIGGER_RESEARCH")

    # Verify story exists in caller's tenant
    story_stmt = select(Story).where(Story.tenant_id == context.tenant_id, Story.id == story_id)
    story_res = await db.execute(story_stmt)
    story = story_res.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    query_topic = (payload and payload.query_topic) or story.title
    opp_id = payload.opportunity_id if payload else None

    job = ResearchJob(
        tenant_id=context.tenant_id,
        story_id=story.id,
        opportunity_id=opp_id,
        query_topic=query_topic,
        status="QUEUED",
        requested_by_user_id=context.user_id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Run research synthesis
    try:
        completed_job = await engine.run_research(
            db=db,
            tenant_id=context.tenant_id,
            research_job_id=job.id,
            user_id=context.user_id,
        )
        return ResearchJobResponse.model_validate(completed_job)
    except Exception as e:
        job.status = "FAILED"
        job.failure_reason = str(e)[:500]
        await db.commit()
        await db.refresh(job)
        return ResearchJobResponse.model_validate(job)


@router.get("/stories/{story_id}/research", response_model=List[ResearchJobResponse])
async def list_story_research_jobs(
    story_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[ResearchJobResponse]:
    """List all research jobs for a story."""
    check_permission(context, "VIEW_RESEARCH")

    story_stmt = select(Story).where(Story.tenant_id == context.tenant_id, Story.id == story_id)
    story_res = await db.execute(story_stmt)
    if not story_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    stmt = (
        select(ResearchJob)
        .where(ResearchJob.tenant_id == context.tenant_id, ResearchJob.story_id == story_id)
        .order_by(ResearchJob.created_at.desc())
    )
    res = await db.execute(stmt)
    jobs = res.scalars().all()
    return [ResearchJobResponse.model_validate(j) for j in jobs]


@router.get("/research/{research_id}", response_model=ResearchJobResponse)
async def get_research_job(
    research_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> ResearchJobResponse:
    """Get research job details."""
    check_permission(context, "VIEW_RESEARCH")

    stmt = select(ResearchJob).where(
        ResearchJob.tenant_id == context.tenant_id, ResearchJob.id == research_id
    )
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research job not found")
    return ResearchJobResponse.model_validate(job)


@router.post("/research/{research_id}/run", response_model=ResearchJobResponse)
async def rerun_research_job(
    research_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> ResearchJobResponse:
    """Re-run an existing research job."""
    check_permission(context, "TRIGGER_RESEARCH")

    stmt = select(ResearchJob).where(
        ResearchJob.tenant_id == context.tenant_id, ResearchJob.id == research_id
    )
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research job not found")

    completed_job = await engine.run_research(
        db=db,
        tenant_id=context.tenant_id,
        research_job_id=job.id,
        user_id=context.user_id,
    )
    return ResearchJobResponse.model_validate(completed_job)


@router.get("/research/{research_id}/evidence", response_model=List[ResearchEvidenceResponse])
async def get_research_evidence(
    research_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[ResearchEvidenceResponse]:
    """List bounded evidence items collected for a research job."""
    check_permission(context, "VIEW_RESEARCH")

    job_stmt = select(ResearchJob).where(
        ResearchJob.tenant_id == context.tenant_id, ResearchJob.id == research_id
    )
    job_res = await db.execute(job_stmt)
    if not job_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research job not found")

    stmt = (
        select(ResearchEvidence)
        .where(
            ResearchEvidence.tenant_id == context.tenant_id,
            ResearchEvidence.research_job_id == research_id,
        )
        .order_by(ResearchEvidence.created_at.asc())
    )
    res = await db.execute(stmt)
    evidence_items = res.scalars().all()
    return [ResearchEvidenceResponse.model_validate(ev) for ev in evidence_items]


@router.get("/research/{research_id}/claims", response_model=List[ResearchClaimResponse])
async def get_research_claims(
    research_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[ResearchClaimResponse]:
    """List factual claims extracted during research."""
    check_permission(context, "VIEW_RESEARCH")

    job_stmt = select(ResearchJob).where(
        ResearchJob.tenant_id == context.tenant_id, ResearchJob.id == research_id
    )
    job_res = await db.execute(job_stmt)
    if not job_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research job not found")

    stmt = (
        select(ResearchClaim)
        .where(
            ResearchClaim.tenant_id == context.tenant_id,
            ResearchClaim.research_job_id == research_id,
        )
        .order_by(ResearchClaim.created_at.asc())
    )
    res = await db.execute(stmt)
    claims = res.scalars().all()
    return [ResearchClaimResponse.model_validate(c) for c in claims]


@router.get("/research/{research_id}/brief", response_model=ResearchBriefResponse)
async def get_research_brief(
    research_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> ResearchBriefResponse:
    """Get the synthesized 5W1H research brief."""
    check_permission(context, "VIEW_RESEARCH")

    stmt = select(ResearchBrief).where(
        ResearchBrief.tenant_id == context.tenant_id,
        ResearchBrief.research_job_id == research_id,
    )
    res = await db.execute(stmt)
    brief = res.scalar_one_or_none()
    if not brief:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Research brief not found"
        )
    return ResearchBriefResponse.model_validate(brief)
