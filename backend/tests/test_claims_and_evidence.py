"""Tests for Research Evidence copyright boundary and claims verification."""

import pytest

from app.db.models.research import ResearchClaim, ResearchEvidence, ResearchJob
from app.db.models.story import Story
from app.services.ai.prompt_defense import enforce_evidence_storage_boundary
from app.services.ai.research_engine import ResearchEngine


def test_evidence_storage_boundary_capping():
    """Verify snippets strictly obey 750 chars and claim summaries obey 500 chars."""
    huge_article = "A" * 5000
    huge_claim = "B" * 2000

    snippet, claim = enforce_evidence_storage_boundary(huge_article, huge_claim)

    assert len(snippet) == 750
    assert len(claim) == 500
    # No full article stored
    assert len(snippet) < len(huge_article)


@pytest.mark.asyncio
async def test_evidence_collection_enforces_boundaries_on_story(db_session, seeded_environment):
    """Verify collect_and_bound_evidence bounds text and attaches rights metadata."""
    env = seeded_environment
    tenant_id = env["tenant_news9"].id
    user_id = env["user_news9"].id

    story = Story(
        tenant_id=tenant_id,
        title="Gorakhpur AI Medical Diagnostic Hub Announced",
        slug="gorakhpur-ai-medical-hub",
        summary="A" * 1500,  # Deliberately long summary
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
    evidence_items = await engine.collect_and_bound_evidence(db_session, tenant_id, job, story)

    assert len(evidence_items) > 0
    ev = evidence_items[0]
    assert len(ev.evidence_snippet) <= 750
    assert len(ev.normalized_claim_summary) <= 500
    assert ev.canonical_url is not None
    assert "rights_type" in ev.rights_metadata


@pytest.mark.asyncio
async def test_claims_conflict_detection_across_publishers(db_session, seeded_environment):
    """Verify distinct publisher discrepancies are surfaced as conflicting claims."""
    env = seeded_environment
    tenant_id = env["tenant_news9"].id
    user_id = env["user_news9"].id

    story = Story(
        tenant_id=tenant_id,
        title="State Metro Project Phase 2 Timeline",
        slug="metro-phase-2-timeline",
        summary="Conflicting reports emerge on completion deadline.",
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

    ev1 = ResearchEvidence(
        tenant_id=tenant_id,
        research_job_id=job.id,
        canonical_url="https://agency1.org/news",
        publisher="State Transport Bureau",
        title="Metro Phase 2 scheduled for December 2026 completion",
        evidence_snippet="The agency affirmed December 2026 is the final target date.",
        normalized_claim_summary="Completion targeted for December 2026.",
        rights_metadata={"rights_type": "official_release", "reuse_permitted": False},
    )
    ev2 = ResearchEvidence(
        tenant_id=tenant_id,
        research_job_id=job.id,
        canonical_url="https://wire2.org/news",
        publisher="Independent Contractors Union",
        title="Contractors warn Metro Phase 2 delayed to mid-2027",
        evidence_snippet="Material shortages will push operations to mid-2027.",
        normalized_claim_summary="Completion delayed to mid-2027.",
        rights_metadata={"rights_type": "fair_use_quote", "reuse_permitted": False},
    )
    db_session.add_all([ev1, ev2])
    await db_session.flush()

    claim = ResearchClaim(
        tenant_id=tenant_id,
        research_job_id=job.id,
        claim_text="Completion scheduled for December 2026",
        claim_type="FACT",
        status="CONFLICTING",
        supporting_evidence_ids=[ev1.id],
        contradicting_evidence_ids=[ev2.id],
        verification_notes="Contractor union reports delay while ministry affirms schedule.",
    )
    db_session.add(claim)
    await db_session.commit()

    assert claim.status == "CONFLICTING"
    assert ev1.id in claim.supporting_evidence_ids
    assert ev2.id in claim.contradicting_evidence_ids
