"""Tests for Structured AI Generation Schemas and Deterministic Fallbacks."""

import pytest
from sqlalchemy import select

from app.db.models.research import ResearchBrief, ResearchClaim, ResearchEvidence, ResearchJob
from app.db.models.story import Story
from app.schemas.research import (
    NarrativeSection,
    ScriptSegment,
    StructuredContentPlanPayload,
    StructuredHeadlinesPayload,
    StructuredScriptPayload,
    StructuredVisualPlanPayload,
    VisualCue,
)
from app.services.ai.research_engine import ResearchEngine


def test_structured_content_plan_schema_valid():
    """Verify Content Plan schema parses and serializes correctly."""
    plan = StructuredContentPlanPayload(
        proposed_angle="Regional economic impact of new expressway",
        target_audience="News 9 Viewers & Commuters",
        key_message="Expressway reduces transit time by 40% but toll costs rise.",
        narrative_structure=[
            NarrativeSection(
                section_title="Route Overview",
                key_points=["Total 120km length", "Connects 4 major industrial nodes"],
                suggested_duration_seconds=30,
            )
        ],
        suggested_format="DIGITAL_EXPLAINER",
        editorial_caveats=["Awaiting final toll schedule notification"],
        confidence_score=0.9,
    )
    assert plan.proposed_angle.startswith("Regional economic")
    assert len(plan.narrative_structure) == 1
    assert plan.narrative_structure[0].suggested_duration_seconds == 30


def test_structured_headlines_schema_clickbait_filter():
    """Verify Headlines schema includes clickbait risk score and evidence traceability."""
    payload = StructuredHeadlinesPayload(
        headlines=[
            {
                "headline": "New Expressway Opens to Public Starting Monday",
                "style_category": "DIRECT",
                "character_count": 48,
                "clickbait_risk_score": 0.05,
                "evidence_basis": "Confirmed by National Highways Authority release",
            },
            {
                "headline": "Will the New Expressway Solve Traffic Woes? Key Facts",
                "style_category": "ANALYTICAL",
                "character_count": 52,
                "clickbait_risk_score": 0.12,
                "evidence_basis": "Urban transit planning statistics",
            },
        ],
        summary_of_angles="Direct announcements and analytical commuter questions",
    )
    assert len(payload.headlines) == 2
    assert payload.headlines[0].clickbait_risk_score < 0.2
    assert payload.headlines[0].evidence_basis != ""


def test_structured_script_schema_fact_vs_allegation():
    """Verify Broadcast Script enforces speaker and status_label segmentation."""
    script = StructuredScriptPayload(
        title="News 9 Primetime Report",
        estimated_duration_seconds=90,
        segments=[
            ScriptSegment(
                segment_number=1,
                segment_type="ANCHOR_INTRO",
                speaker="Anchor",
                spoken_text="Good evening. We start with verified updates from the district court.",
                visual_cue="Anchor wide to medium close-up",
                status_label="CONFIRMED_FACT",
            ),
            ScriptSegment(
                segment_number=2,
                segment_type="EVIDENCE_READ",
                speaker="Anchor",
                spoken_text="Opposition leaders alleged procedural irregularities.",
                visual_cue="Full screen graphic with attribution quote marks",
                status_label="ATTRIBUTED_CLAIM",
            ),
        ],
        compliance_notes=["Ensure quote attribution is maintained on-screen"],
    )
    assert len(script.segments) == 2
    assert script.segments[0].status_label == "CONFIRMED_FACT"
    assert script.segments[1].status_label == "ATTRIBUTED_CLAIM"


def test_structured_visual_plan_is_purely_textual():
    """Verify visual plan strictly contains textual cues without media assets."""
    vp = StructuredVisualPlanPayload(
        recommended_visual_format="16:9 HD Broadcast Package",
        visual_cues=[
            VisualCue(
                cue_id="VC-1",
                cue_type="MAP_OVERLAY",
                description="Highlight Gorakhpur to Lucknow travel route in cyan",
                on_screen_text="Corridor Map: 120km",
            )
        ],
        production_guidelines=["Keep text within safe title boundaries"],
    )
    assert len(vp.visual_cues) == 1
    assert vp.visual_cues[0].cue_type == "MAP_OVERLAY"


@pytest.mark.asyncio
async def test_deterministic_research_fallback_when_model_offline(db_session, seeded_environment):
    """Verify ResearchEngine fallback synthesizes a clean brief when Ollama is offline."""

    env = seeded_environment
    tenant_id = env["tenant_news9"].id
    user_id = env["user_news9"].id

    story = Story(
        tenant_id=tenant_id,
        title="Gorakhpur IT Park Phase 1 Inauguration",
        slug="gorakhpur-it-park-inauguration",
        summary="State government inaugurates new tech hub creating 2,000 local jobs.",
        created_by_user_id=user_id,
    )
    db_session.add(story)
    await db_session.flush()

    job = ResearchJob(
        tenant_id=tenant_id,
        story_id=story.id,
        query_topic=story.title,
        requested_by_user_id=user_id,
    )
    db_session.add(job)
    await db_session.flush()

    engine = ResearchEngine()
    completed_job = await engine.run_research(db_session, tenant_id, job.id, user_id)

    assert completed_job.status == "COMPLETED"
    assert completed_job.completed_at is not None

    ev_res = await db_session.execute(
        select(ResearchEvidence).where(ResearchEvidence.research_job_id == completed_job.id)
    )
    evidence_items = ev_res.scalars().all()
    assert len(evidence_items) > 0

    brief_res = await db_session.execute(
        select(ResearchBrief).where(ResearchBrief.research_job_id == completed_job.id)
    )
    brief = brief_res.scalar_one_or_none()
    assert brief is not None
    assert "Gorakhpur IT Park" in brief.what_happened

    cl_res = await db_session.execute(
        select(ResearchClaim).where(ResearchClaim.research_job_id == completed_job.id)
    )
    claims = cl_res.scalars().all()
    assert len(claims) > 0

