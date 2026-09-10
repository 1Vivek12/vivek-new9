"""API endpoints for Phase 4 AI Content Generation and Human Review Gate."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import check_permission
from app.core.tenant import TenantContext, get_tenant_context
from app.db.models.research import AIOutput, ResearchJob
from app.db.models.story import Story
from app.db.session import get_db_session
from app.schemas.research import (
    AIOutputActionRequest,
    AIOutputEditRequest,
    AIOutputResponse,
    ContentPlanGenerateRequest,
    HeadlinesGenerateRequest,
    ScriptGenerateRequest,
    SEOGenerateRequest,
    VisualPlanGenerateRequest,
)
from app.services.ai.research_engine import ResearchEngine

router = APIRouter(tags=["AI Content Generation & Editorial Review"])
engine = ResearchEngine()


async def _get_latest_research_job_id(db: AsyncSession, tenant_id: str, story_id: str) -> str:
    """Helper to locate or auto-trigger the research job for an editorial story."""
    stmt = (
        select(ResearchJob)
        .where(ResearchJob.tenant_id == tenant_id, ResearchJob.story_id == story_id)
        .order_by(ResearchJob.created_at.desc())
    )
    res = await db.execute(stmt)
    job = res.scalars().first()
    if job:
        return job.id

    # If no research job exists, create and run one
    story = await db.get(Story, story_id)
    if not story or story.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    new_job = ResearchJob(
        tenant_id=tenant_id,
        story_id=story.id,
        query_topic=story.title,
        status="QUEUED",
        requested_by_user_id=story.created_by_user_id,
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)

    completed_job = await engine.run_research(
        db=db,
        tenant_id=tenant_id,
        research_job_id=new_job.id,
        user_id=story.created_by_user_id,
    )
    return completed_job.id


@router.post(
    "/stories/{story_id}/content-plan",
    response_model=AIOutputResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_content_plan(
    story_id: str,
    payload: Optional[ContentPlanGenerateRequest] = None,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> AIOutputResponse:
    """Generate an AI Content Plan for human editorial review."""
    check_permission(context, "GENERATE_AI_CONTENT")
    job_id = await _get_latest_research_job_id(db, context.tenant_id, story_id)

    ai_output = await engine.generate_content_plan(
        db=db,
        tenant_id=context.tenant_id,
        story_id=story_id,
        research_job_id=job_id,
        user_id=context.user_id,
        editorial_angle=payload.editorial_angle if payload else None,
        target_audience=payload.target_audience if payload else None,
    )
    return AIOutputResponse.model_validate(ai_output)


@router.post(
    "/stories/{story_id}/headlines",
    response_model=AIOutputResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_headlines(
    story_id: str,
    payload: Optional[HeadlinesGenerateRequest] = None,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> AIOutputResponse:
    """Generate headline variants strictly filtered for clickbait and defamation."""
    check_permission(context, "GENERATE_AI_CONTENT")
    job_id = await _get_latest_research_job_id(db, context.tenant_id, story_id)

    ai_output = await engine.generate_headlines(
        db=db,
        tenant_id=context.tenant_id,
        story_id=story_id,
        research_job_id=job_id,
        user_id=context.user_id,
        count=(payload.count if payload else 5),
        focus=(payload.focus if payload else None),
    )
    return AIOutputResponse.model_validate(ai_output)


@router.post(
    "/stories/{story_id}/script",
    response_model=AIOutputResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_script(
    story_id: str,
    payload: Optional[ScriptGenerateRequest] = None,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> AIOutputResponse:
    """Generate broadcast news script distinguishing Fact vs Allegation vs Developing."""
    check_permission(context, "GENERATE_AI_CONTENT")
    job_id = await _get_latest_research_job_id(db, context.tenant_id, story_id)

    ai_output = await engine.generate_script(
        db=db,
        tenant_id=context.tenant_id,
        story_id=story_id,
        research_job_id=job_id,
        user_id=context.user_id,
        script_format=(payload.script_format if payload else "TV_NEWS_RUNDOWN"),
        target_duration_seconds=(payload.target_duration_seconds if payload else 90),
    )
    return AIOutputResponse.model_validate(ai_output)


@router.post(
    "/stories/{story_id}/seo",
    response_model=AIOutputResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_seo(
    story_id: str,
    payload: Optional[SEOGenerateRequest] = None,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> AIOutputResponse:
    """Generate SEO metadata."""
    check_permission(context, "GENERATE_AI_CONTENT")
    job_id = await _get_latest_research_job_id(db, context.tenant_id, story_id)

    ai_output = await engine.generate_seo(
        db=db,
        tenant_id=context.tenant_id,
        story_id=story_id,
        research_job_id=job_id,
        user_id=context.user_id,
        target_keyword=(payload.target_keyword if payload else None),
    )
    return AIOutputResponse.model_validate(ai_output)


@router.post(
    "/stories/{story_id}/visual-plan",
    response_model=AIOutputResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_visual_plan(
    story_id: str,
    payload: Optional[VisualPlanGenerateRequest] = None,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> AIOutputResponse:
    """Generate textual visual cues (anchor intro, maps, document graphics)."""
    check_permission(context, "GENERATE_AI_CONTENT")
    job_id = await _get_latest_research_job_id(db, context.tenant_id, story_id)

    ai_output = await engine.generate_visual_plan(
        db=db,
        tenant_id=context.tenant_id,
        story_id=story_id,
        research_job_id=job_id,
        user_id=context.user_id,
        visual_style=(payload.visual_style if payload else None),
    )
    return AIOutputResponse.model_validate(ai_output)


@router.get("/stories/{story_id}/ai-outputs", response_model=List[AIOutputResponse])
async def list_story_ai_outputs(
    story_id: str,
    output_type: Optional[str] = Query(None),
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> List[AIOutputResponse]:
    """List all AI output versions generated for a story."""
    check_permission(context, "VIEW_EDITORIAL")

    stmt = select(AIOutput).where(
        AIOutput.tenant_id == context.tenant_id, AIOutput.story_id == story_id
    )
    if output_type:
        stmt = stmt.where(AIOutput.output_type == output_type.upper())
    stmt = stmt.order_by(AIOutput.created_at.desc())

    res = await db.execute(stmt)
    outputs = res.scalars().all()
    return [AIOutputResponse.model_validate(o) for o in outputs]


@router.get("/ai-outputs/{output_id}", response_model=AIOutputResponse)
async def get_ai_output(
    output_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> AIOutputResponse:
    """Get single AI output item."""
    check_permission(context, "VIEW_EDITORIAL")

    output = await db.get(AIOutput, output_id)
    if not output or output.tenant_id != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI output not found")
    return AIOutputResponse.model_validate(output)


# ---------------------------------------------------------------------------
# Human Editorial Review Gate Controls
# ---------------------------------------------------------------------------


@router.post("/ai-outputs/{output_id}/accept", response_model=AIOutputResponse)
async def accept_ai_output(
    output_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> AIOutputResponse:
    """Human editorial action: Accept AI output."""
    check_permission(context, "REVIEW_AI_CONTENT")

    try:
        updated = await engine.review_output(
            db=db,
            tenant_id=context.tenant_id,
            output_id=output_id,
            user_id=context.user_id,
            action="ACCEPT",
        )
        return AIOutputResponse.model_validate(updated)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/ai-outputs/{output_id}/reject", response_model=AIOutputResponse)
async def reject_ai_output(
    output_id: str,
    payload: AIOutputActionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> AIOutputResponse:
    """Human editorial action: Reject AI output with mandatory reason."""
    check_permission(context, "REVIEW_AI_CONTENT")

    if not payload.rejection_reason or not payload.rejection_reason.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rejection reason is mandatory when rejecting AI output",
        )

    try:
        updated = await engine.review_output(
            db=db,
            tenant_id=context.tenant_id,
            output_id=output_id,
            user_id=context.user_id,
            action="REJECT",
            rejection_reason=payload.rejection_reason,
        )
        return AIOutputResponse.model_validate(updated)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/ai-outputs/{output_id}/edit", response_model=AIOutputResponse)
async def edit_ai_output(
    output_id: str,
    payload: AIOutputEditRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db_session),
) -> AIOutputResponse:
    """Human editorial action: Edit / revise AI output content."""
    check_permission(context, "REVIEW_AI_CONTENT")

    try:
        updated = await engine.edit_output(
            db=db,
            tenant_id=context.tenant_id,
            output_id=output_id,
            user_id=context.user_id,
            edited_content=payload.content,
        )
        return AIOutputResponse.model_validate(updated)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


