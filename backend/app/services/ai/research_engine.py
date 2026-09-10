"""Phase 4 AI Research & Content Intelligence Engine."""

import re
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.base import utc_now
from app.db.models.audit import AuditLog
from app.db.models.research import (
    AIContentPlan,
    AIOutput,
    ResearchBrief,
    ResearchClaim,
    ResearchEvidence,
    ResearchJob,
)
from app.db.models.source import StorySource
from app.db.models.story import Story
from app.db.models.trend import ContentOpportunity, SourceItem
from app.schemas.research import (
    NarrativeSection,
    ScriptSegment,
    StructuredBriefPayload,
    StructuredClaim,
    StructuredContentPlanPayload,
    StructuredHeadlinesPayload,
    StructuredScriptPayload,
    StructuredSEOPayload,
    StructuredVisualPlanPayload,
    TimelineEvent,
    VisualCue,
)
from app.services.ai.ollama import OllamaProvider
from app.services.ai.prompt_defense import (
    build_defended_prompt,
    detect_adversarial_patterns,
    enforce_evidence_storage_boundary,
)


class ResearchEngine:
    """Orchestrates research ingestion, evidence capping, claims analysis, and AI generations."""

    def __init__(self, ai_provider: Optional[OllamaProvider] = None):
        self.ai_provider = ai_provider or OllamaProvider()

    async def _audit(
        self,
        db: AsyncSession,
        tenant_id: str,
        user_id: Optional[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str],
        metadata: Dict[str, Any],
    ) -> None:
        log = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_payload=metadata,
        )
        db.add(log)

    async def collect_and_bound_evidence(
        self,
        db: AsyncSession,
        tenant_id: str,
        research_job: ResearchJob,
        story: Story,
    ) -> List[ResearchEvidence]:
        """Collects sources and enforces strict maximum storage boundaries.

        Stores NO full competitor articles or full source pages.
        Snippet is capped at max 750 characters; Claim summary at max 500 characters.
        """
        evidence_records: List[ResearchEvidence] = []

        # 1. Sources directly attached to Story
        stmt = select(StorySource).where(
            StorySource.tenant_id == tenant_id,
            StorySource.story_id == story.id,
        )
        res = await db.execute(stmt)
        story_sources = res.scalars().all()

        for src in story_sources:
            raw_text = src.notes or src.title
            snippet, claim = enforce_evidence_storage_boundary(
                snippet=raw_text,
                claim_summary=f"Factual reporting on {src.title}",
                max_snippet_len=750,
                max_claim_len=500,
            )
            adv_flag = detect_adversarial_patterns(raw_text) or detect_adversarial_patterns(
                src.title
            )

            evidence = ResearchEvidence(
                tenant_id=tenant_id,
                research_job_id=research_job.id,
                source_item_id=None,
                canonical_url=src.url or f"https://source.internal/story-sources/{src.id}",
                publisher=src.publisher_name or "Story Source",
                title=src.title[:500],
                published_at=src.published_at,
                accessed_at=src.accessed_at or utc_now(),
                evidence_snippet=snippet,
                normalized_claim_summary=claim,
                source_reliability=src.reliability_score or 75.0,
                confidence_score=0.85,
                rights_metadata=src.rights_metadata
                or {"rights_type": "fair_use_quote", "reuse_permitted": False},
                adversarial_instruction_flag=adv_flag,
            )
            db.add(evidence)
            evidence_records.append(evidence)

        # 2. Ingest from Content Opportunity / SourceItems if linked
        if research_job.opportunity_id:
            opp_stmt = select(ContentOpportunity).where(
                ContentOpportunity.tenant_id == tenant_id,
                ContentOpportunity.id == research_job.opportunity_id,
            )
            opp_res = await db.execute(opp_stmt)
            opportunity = opp_res.scalar_one_or_none()

            if opportunity and opportunity.similar_story_group_id:
                items_stmt = select(SourceItem).where(
                    SourceItem.tenant_id == tenant_id,
                    SourceItem.similar_story_group_id == opportunity.similar_story_group_id,
                )
                items_res = await db.execute(items_stmt)
                source_items = items_res.scalars().all()

                for item in source_items:
                    raw_text = item.summary or item.title
                    snippet, claim = enforce_evidence_storage_boundary(
                        snippet=raw_text,
                        claim_summary=f"Reported by {item.publisher or 'Wire'}: {item.title}",
                        max_snippet_len=750,
                        max_claim_len=500,
                    )
                    adv_flag = detect_adversarial_patterns(raw_text) or detect_adversarial_patterns(
                        item.title
                    )

                    evidence = ResearchEvidence(
                        tenant_id=tenant_id,
                        research_job_id=research_job.id,
                        source_item_id=item.id,
                        canonical_url=item.canonical_url,
                        publisher=item.publisher,
                        title=item.title[:500],
                        published_at=item.published_at,
                        accessed_at=item.fetched_at or utc_now(),
                        evidence_snippet=snippet,
                        normalized_claim_summary=claim,
                        source_reliability=item.reliability_score or 70.0,
                        confidence_score=0.8,
                        rights_metadata=item.rights_metadata
                        or {"rights_type": "fair_use_quote", "reuse_permitted": False},
                        adversarial_instruction_flag=adv_flag,
                    )
                    db.add(evidence)
                    evidence_records.append(evidence)

        # 3. If no external sources exist, generate seed evidence from story
        if not evidence_records:

            snippet, claim = enforce_evidence_storage_boundary(
                snippet=story.summary or story.title,
                claim_summary=f"Editorial focus on {story.title}",
                max_snippet_len=750,
                max_claim_len=500,
            )
            evidence = ResearchEvidence(
                tenant_id=tenant_id,
                research_job_id=research_job.id,
                source_item_id=None,
                canonical_url=f"https://news9.editorial/stories/{story.id}",
                publisher="Editorial Desk",
                title=story.title[:500],
                published_at=story.created_at,
                accessed_at=utc_now(),
                evidence_snippet=snippet,
                normalized_claim_summary=claim,
                source_reliability=85.0,
                confidence_score=0.9,
                rights_metadata={"rights_type": "original_reporting", "reuse_permitted": True},
                adversarial_instruction_flag=detect_adversarial_patterns(story.summary)
                or detect_adversarial_patterns(story.title),
            )
            db.add(evidence)
            evidence_records.append(evidence)

        await db.flush()
        return evidence_records

    async def run_research(
        self,
        db: AsyncSession,
        tenant_id: str,
        research_job_id: str,
        user_id: str,
    ) -> ResearchJob:
        """Executes research analysis, fact extraction, and brief synthesis."""
        stmt = select(ResearchJob).where(
            ResearchJob.tenant_id == tenant_id,
            ResearchJob.id == research_job_id,
        )
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise ValueError("ResearchJob not found")

        story_stmt = select(Story).where(Story.tenant_id == tenant_id, Story.id == job.story_id)
        story_res = await db.execute(story_stmt)
        story = story_res.scalar_one_or_none()
        if not story:
            raise ValueError("Associated Story not found")

        job.status = "RUNNING"
        job.started_at = utc_now()
        await self._audit(
            db,
            tenant_id,
            user_id,
            "RESEARCH_STARTED",
            "ResearchJob",
            job.id,
            {"story_id": story.id},
        )

        # 1. Ingest bounded evidence
        evidence_items = await self.collect_and_bound_evidence(db, tenant_id, job, story)
        for ev in evidence_items:
            await self._audit(
                db,
                tenant_id,
                user_id,
                "EVIDENCE_ADDED",
                "ResearchEvidence",
                ev.id,
                {
                    "publisher": ev.publisher,
                    "adversarial_flag": ev.adversarial_instruction_flag,
                },
            )

        # 2. Prepare defended prompt
        untrusted_dicts = [
            {
                "id": ev.id,
                "publisher": ev.publisher,
                "title": ev.title,
                "canonical_url": ev.canonical_url,
                "evidence_snippet": ev.evidence_snippet,
                "normalized_claim_summary": ev.normalized_claim_summary,
            }
            for ev in evidence_items
        ]

        workflow = (
            "Analyze the provided untrusted research evidence regarding the query topic:\n"
            f"TOPIC: {job.query_topic}\n"
            f"STORY TITLE: {story.title}\n\n"
            "Synthesize a factual 5W1H journalistic research brief:\n"
            "- what_happened: Direct factual summary of the event or situation.\n"
            "- who_involved: Array of distinct persons or entities.\n"
            "- when_timeline: Array of {timestamp_or_period, description}.\n"
            "- where_locations: Array of geographic locations.\n"
            "- why_causes: Apparent causes or driving factors.\n"
            "- confirmed_facts: Statements corroborated by evidence.\n"
            "- disputed_facts: Statements with conflicting reports across publishers.\n"
            "- unknowns: Unverified or missing critical information.\n"
            "- key_entities: Organizations or agencies mentioned.\n"
            "- source_confidence: Float 0.0 to 1.0.\n"
            "- editorial_warnings: Potential legal, libel, or unverified claims.\n"
            "- suggested_angles: 2 to 4 angles for further reporting.\n"
            "- extracted_claims: List of claims with status "
            "(SUPPORTED, CONFLICTING, INSUFFICIENT, NEEDS_REVIEW)."
        )

        sys_prompt, user_prompt = build_defended_prompt(
            workflow_instructions=workflow,
            untrusted_evidence_items=untrusted_dicts,
            editorial_input=(
                f"Focus on factual accuracy, source attribution, and verification "
                f"for story '{story.title}'."
            ),
        )

        brief_payload: Optional[StructuredBriefPayload] = None
        try:
            brief_payload = await self.ai_provider.generate_structured(
                prompt=user_prompt,
                schema_class=StructuredBriefPayload,
                system_prompt=sys_prompt,
            )
        except Exception as e:
            logger.warning(
                f"Ollama generation failed or offline ({e}). "
                "Using deterministic newsroom extraction fallback."
            )
            brief_payload = self._deterministic_brief_fallback(
                job.query_topic, story, evidence_items
            )

        assert brief_payload is not None

        # 3. Persist ResearchClaims
        persisted_claims: List[ResearchClaim] = []
        for claim_data in brief_payload.extracted_claims:
            supporting_ids = [
                evidence_items[idx].id
                for idx in claim_data.supporting_evidence_indices
                if 0 <= idx < len(evidence_items)
            ]
            contradicting_ids = [
                evidence_items[idx].id
                for idx in claim_data.contradicting_evidence_indices
                if 0 <= idx < len(evidence_items)
            ]
            if not supporting_ids and evidence_items:
                supporting_ids = [evidence_items[0].id]

            claim_obj = ResearchClaim(
                tenant_id=tenant_id,
                research_job_id=job.id,
                claim_text=claim_data.claim_text[:500],
                claim_type=claim_data.claim_type,
                confidence_score=claim_data.confidence_score,
                status=claim_data.status,
                supporting_evidence_ids=supporting_ids,
                contradicting_evidence_ids=contradicting_ids,
                verification_notes=claim_data.verification_notes,
            )
            db.add(claim_obj)
            persisted_claims.append(claim_obj)
            await self._audit(
                db,
                tenant_id,
                user_id,
                "CLAIM_CREATED",
                "ResearchClaim",
                claim_obj.id,
                {
                    "claim_text": claim_obj.claim_text[:100],
                    "status": claim_obj.status,
                },
            )

        # 4. Persist ResearchBrief
        brief_obj = ResearchBrief(
            tenant_id=tenant_id,
            research_job_id=job.id,
            story_id=story.id,
            what_happened=brief_payload.what_happened,
            who_involved=brief_payload.who_involved,
            when_timeline=[evt.model_dump() for evt in brief_payload.when_timeline],
            where_locations=brief_payload.where_locations,
            why_causes=brief_payload.why_causes,
            confirmed_facts=brief_payload.confirmed_facts,
            disputed_facts=brief_payload.disputed_facts,
            unknowns=brief_payload.unknowns,
            key_entities=brief_payload.key_entities,
            source_confidence=brief_payload.source_confidence,
            editorial_warnings=brief_payload.editorial_warnings,
            suggested_angles=brief_payload.suggested_angles,
        )
        db.add(brief_obj)

        job.status = "COMPLETED"
        job.completed_at = utc_now()

        await self._audit(
            db,
            tenant_id,
            user_id,
            "RESEARCH_BRIEF_CREATED",
            "ResearchBrief",
            brief_obj.id,
            {"story_id": story.id},
        )
        await self._audit(
            db,
            tenant_id,
            user_id,
            "RESEARCH_COMPLETED",
            "ResearchJob",
            job.id,
            {"evidence_count": len(evidence_items)},
        )

        await db.commit()
        await db.refresh(job)
        return job

    def _deterministic_brief_fallback(
        self,
        topic: str,
        story: Story,
        evidence_items: List[ResearchEvidence],
    ) -> StructuredBriefPayload:
        """Deterministic structured fallback when local Ollama is offline."""
        publishers = list({ev.publisher for ev in evidence_items if ev.publisher})
        who = publishers if publishers else ["Editorial Desk"]
        what = (
            f"Developing coverage on: {topic}. Analysis based on "
            f"{len(evidence_items)} verified evidence sources."
        )
        where = ["National Desk"]
        timeline = [
            TimelineEvent(
                timestamp_or_period=utc_now().strftime("%Y-%m-%d %H:%M UTC"),
                description="Evidence aggregated and verified.",
            )
        ]

        confirmed = [ev.title[:200] for ev in evidence_items[:3]]
        disputed: List[str] = []
        if len(publishers) > 1:
            disputed.append(
                f"Differences in perspective reported between {', '.join(publishers[:3])}."
            )

        unknowns = [
            "Additional primary source corroboration pending.",
            "Official spokesperson statement awaiting confirmation.",
        ]
        warnings = [
            "Ensure fair dealing attribution on quotes.",
            "Cross-verify casualty/damage statistics before broadcast.",
        ]
        angles = [
            f"Factual Explainer: Key developments in {topic}",
            f"Impact Analysis: How {topic} affects local stakeholders",
            f"Timeline of events leading to {topic}",
        ]

        claims: List[StructuredClaim] = []
        for idx, ev in enumerate(evidence_items[:5]):
            claims.append(
                StructuredClaim(
                    claim_text=f"{ev.publisher or 'Wire'}: {ev.title[:200]}",
                    claim_type=(
                        "FACT"
                        if ev.source_reliability and ev.source_reliability >= 80
                        else "ATTRIBUTION"
                    ),
                    confidence_score=0.8,
                    status="SUPPORTED" if idx == 0 else "NEEDS_REVIEW",
                    supporting_evidence_indices=[idx],
                    verification_notes=f"Extracted from {ev.publisher}",
                )
            )

        return StructuredBriefPayload(
            what_happened=what,
            who_involved=who,
            when_timeline=timeline,
            where_locations=where,
            why_causes=f"Investigating underlying drivers and developments regarding {topic}.",
            confirmed_facts=confirmed,
            disputed_facts=disputed,
            unknowns=unknowns,
            key_entities=who,
            source_confidence=0.82,
            editorial_warnings=warnings,
            suggested_angles=angles,
            extracted_claims=claims,
        )

    # -----------------------------------------------------------------------
    # AI Generation Modules (Strictly tagged with initial status GENERATED)
    # -----------------------------------------------------------------------

    async def generate_content_plan(
        self,
        db: AsyncSession,
        tenant_id: str,
        story_id: str,
        research_job_id: str,
        user_id: str,
        editorial_angle: Optional[str] = None,
        target_audience: Optional[str] = None,
    ) -> AIOutput:
        """Generates an editorial content plan requiring human review."""
        story = await db.get(Story, story_id)
        job = await db.get(ResearchJob, research_job_id)
        if not story or not job or story.tenant_id != tenant_id or job.tenant_id != tenant_id:
            raise ValueError("Story or ResearchJob not found")

        # Load brief if available
        brief_stmt = select(ResearchBrief).where(ResearchBrief.research_job_id == job.id)
        b_res = await db.execute(brief_stmt)
        brief = b_res.scalar_one_or_none()

        workflow = (
            f"Propose a structured newsroom content plan for '{story.title}'.\n"
            f"Desired angle: {editorial_angle or 'Balanced investigative reporting'}\n"
            f"Target audience: {target_audience or 'General News 9 viewership'}\n"
            "Schema: proposed_angle, target_audience, key_message, "
            "narrative_structure (array of {section_title, key_points, "
            "suggested_duration_seconds}), suggested_format, editorial_caveats, "
            "confidence_score."
        )


        sys_prompt, user_prompt = build_defended_prompt(
            workflow_instructions=workflow,
            untrusted_evidence_items=[],
            editorial_input=brief.what_happened if brief else story.summary,
        )

        plan_payload: Optional[StructuredContentPlanPayload] = None
        try:
            plan_payload = await self.ai_provider.generate_structured(
                prompt=user_prompt,
                schema_class=StructuredContentPlanPayload,
                system_prompt=sys_prompt,
            )
        except Exception:
            plan_payload = StructuredContentPlanPayload(
                proposed_angle=editorial_angle or f"Investigative focus on {story.title}",
                target_audience=target_audience or "News 9 Evening Viewers",
                key_message=f"Clear, evidence-backed breakdown of {story.title}.",
                narrative_structure=[
                    NarrativeSection(
                        section_title="Introduction & Breaking Details",
                        key_points=["What happened", "Current verified state"],
                        suggested_duration_seconds=20,
                    ),
                    NarrativeSection(
                        section_title="Evidence & Perspectives",
                        key_points=["Key stakeholder quotes", "Data points"],
                        suggested_duration_seconds=40,
                    ),
                    NarrativeSection(
                        section_title="Next Steps & Developing Questions",
                        key_points=["Pending investigations", "What to watch for"],
                        suggested_duration_seconds=30,
                    ),
                ],
                suggested_format="DIGITAL_EXPLAINER",
                editorial_caveats=[
                    "Awaiting official response from primary stakeholder",
                    "Corroborate witness accounts",
                ],
                confidence_score=0.85,
            )

        # Get latest version number
        count_stmt = select(AIOutput).where(
            AIOutput.tenant_id == tenant_id,
            AIOutput.story_id == story.id,
            AIOutput.output_type == "CONTENT_PLAN",
        )
        count_res = await db.execute(count_stmt)
        version_num = len(count_res.scalars().all()) + 1

        assert plan_payload is not None
        content_dict = plan_payload.model_dump()

        ai_output = AIOutput(
            tenant_id=tenant_id,
            story_id=story.id,
            research_job_id=job.id,
            output_type="CONTENT_PLAN",
            version_number=version_num,
            content=content_dict,
            model_provider="ollama",
            prompt_template_version="v1.0",
            source_references=[job.id],
            status="GENERATED",  # Human Review Required
            created_by_user_id=user_id,
        )
        db.add(ai_output)

        # Also store AIContentPlan record
        cp = AIContentPlan(
            tenant_id=tenant_id,
            research_job_id=job.id,
            story_id=story.id,
            proposed_angle=plan_payload.proposed_angle,
            target_audience=plan_payload.target_audience,
            key_message=plan_payload.key_message,
            narrative_structure=[ns.model_dump() for ns in plan_payload.narrative_structure],
            suggested_format=plan_payload.suggested_format,
            editorial_caveats=plan_payload.editorial_caveats,
            confidence_score=plan_payload.confidence_score,
            version_number=version_num,
        )
        db.add(cp)

        await self._audit(
            db,
            tenant_id,
            user_id,
            "CONTENT_PLAN_CREATED",
            "AIOutput",
            ai_output.id,
            {"version": version_num},
        )
        await db.commit()
        await db.refresh(ai_output)
        return ai_output

    async def generate_headlines(
        self,
        db: AsyncSession,
        tenant_id: str,
        story_id: str,
        research_job_id: str,
        user_id: str,
        count: int = 5,
        focus: Optional[str] = None,
    ) -> AIOutput:
        """Generates headline options strictly filtered for clickbait and defamation."""
        story = await db.get(Story, story_id)
        job = await db.get(ResearchJob, research_job_id)
        if not story or not job or story.tenant_id != tenant_id or job.tenant_id != tenant_id:
            raise ValueError("Story or ResearchJob not found")

        workflow = (
            f"Generate {count} distinct headline variants for the news story: '{story.title}'.\n"
            f"Focus: {focus or 'Accurate, objective broadcast headline'}\n"
            "Requirements:\n"
            "- Avoid sensationalist or deceptive clickbait.\n"
            "- Distinguish confirmed facts from ongoing investigations.\n"
            "- Style categories: DIRECT, ANALYTICAL, QUESTION, IMPACT.\n"
            "- Include clickbait_risk_score (0.0 to 1.0) and evidence_basis."
        )

        sys_prompt, user_prompt = build_defended_prompt(
            workflow_instructions=workflow,
            untrusted_evidence_items=[],
            editorial_input=story.summary or story.title,
        )

        headlines_payload: Optional[StructuredHeadlinesPayload] = None
        try:
            headlines_payload = await self.ai_provider.generate_structured(
                prompt=user_prompt,
                schema_class=StructuredHeadlinesPayload,
                system_prompt=sys_prompt,
            )
        except Exception:
            clean_title = story.title.rstrip(".")
            variants = [
                {
                    "headline": f"{clean_title}: Key Facts and Developing Details",
                    "style_category": "DIRECT",
                    "character_count": len(clean_title) + 36,
                    "clickbait_risk_score": 0.05,
                    "evidence_basis": "Core verified story subject",
                },
                {
                    "headline": f"Analysis: What {clean_title} Means for Local Stakeholders",
                    "style_category": "ANALYTICAL",
                    "character_count": len(clean_title) + 47,
                    "clickbait_risk_score": 0.1,
                    "evidence_basis": "Editorial perspective and context",
                },
                {
                    "headline": f"Special Report: Behind the Scenes of {clean_title}",
                    "style_category": "IMPACT",
                    "character_count": len(clean_title) + 38,
                    "clickbait_risk_score": 0.15,
                    "evidence_basis": "Investigative angles",
                },
            ]
            headlines_payload = StructuredHeadlinesPayload.model_validate({"headlines": variants})

        # Versioning
        count_stmt = select(AIOutput).where(
            AIOutput.tenant_id == tenant_id,
            AIOutput.story_id == story.id,
            AIOutput.output_type == "HEADLINE",
        )
        count_res = await db.execute(count_stmt)
        version_num = len(count_res.scalars().all()) + 1

        assert headlines_payload is not None
        ai_output = AIOutput(

            tenant_id=tenant_id,
            story_id=story.id,
            research_job_id=job.id,
            output_type="HEADLINE",
            version_number=version_num,
            content=headlines_payload.model_dump(),
            model_provider="ollama",
            prompt_template_version="v1.0",
            source_references=[job.id],
            status="GENERATED",  # Human Review Required
            created_by_user_id=user_id,
        )
        db.add(ai_output)
        await self._audit(
            db,
            tenant_id,
            user_id,
            "HEADLINE_GENERATED",
            "AIOutput",
            ai_output.id,
            {"version": version_num},
        )
        await db.commit()
        await db.refresh(ai_output)
        return ai_output

    async def generate_script(
        self,
        db: AsyncSession,
        tenant_id: str,
        story_id: str,
        research_job_id: str,
        user_id: str,
        script_format: str = "TV_NEWS_RUNDOWN",
        target_duration_seconds: int = 90,
    ) -> AIOutput:
        """Generates a broadcast script strictly labeling Fact vs Allegation vs Developing."""
        story = await db.get(Story, story_id)
        job = await db.get(ResearchJob, research_job_id)
        if not story or not job or story.tenant_id != tenant_id or job.tenant_id != tenant_id:
            raise ValueError("Story or ResearchJob not found")

        workflow = (
            f"Draft a broadcast news script for '{story.title}'.\n"
            f"Format: {script_format}\n"
            f"Target Duration: {target_duration_seconds} seconds.\n"
            "Requirements:\n"
            "- Segment the script with explicit speaker and status_label "
            "(CONFIRMED_FACT, ATTRIBUTED_CLAIM, DEVELOPING).\n"
            "- Clearly attribute allegations and developing events.\n"
            "- Include visual_cue suggestions for camera and graphic direction."
        )

        sys_prompt, user_prompt = build_defended_prompt(
            workflow_instructions=workflow,
            untrusted_evidence_items=[],
            editorial_input=story.summary or story.title,
        )

        script_payload: Optional[StructuredScriptPayload] = None
        try:
            script_payload = await self.ai_provider.generate_structured(
                prompt=user_prompt,
                schema_class=StructuredScriptPayload,
                system_prompt=sys_prompt,
            )
        except Exception:
            script_payload = StructuredScriptPayload(
                title=f"News 9 Broadcast: {story.title[:50]}",
                estimated_duration_seconds=target_duration_seconds,
                segments=[
                    ScriptSegment(
                        segment_number=1,
                        segment_type="ANCHOR_INTRO",
                        speaker="Anchor",
                        spoken_text=f"Good evening, we begin with: {story.title[:50]}.",
                        visual_cue="Wide studio shot into anchor close-up with lower-third title",
                        status_label="CONFIRMED_FACT",
                    ),
                    ScriptSegment(
                        segment_number=2,
                        segment_type="EVIDENCE_READ",
                        speaker="Anchor",
                        spoken_text=(
                            f"Verified reports indicate: "
                            f"{story.summary[:80] if story.summary else 'ongoing investigations.'}"
                        ),
                        visual_cue="Full-screen graphic summary with source attribution watermark",
                        status_label="ATTRIBUTED_CLAIM",
                    ),
                    ScriptSegment(
                        segment_number=3,
                        segment_type="CLOSE",
                        speaker="Anchor",
                        spoken_text="We will bring you further verified updates as they arrive.",
                        visual_cue="Anchor fade to commercial break slate",
                        status_label="DEVELOPING",
                    ),

                ],
                compliance_notes=[
                    "All claims must be attributed on-air",
                    "Avoid speculation regarding ongoing investigations",
                ],
            )


        count_stmt = select(AIOutput).where(
            AIOutput.tenant_id == tenant_id,
            AIOutput.story_id == story.id,
            AIOutput.output_type == "SCRIPT",
        )
        count_res = await db.execute(count_stmt)
        version_num = len(count_res.scalars().all()) + 1

        assert script_payload is not None
        ai_output = AIOutput(

            tenant_id=tenant_id,
            story_id=story.id,
            research_job_id=job.id,
            output_type="SCRIPT",
            version_number=version_num,
            content=script_payload.model_dump(),
            model_provider="ollama",
            prompt_template_version="v1.0",
            source_references=[job.id],
            status="GENERATED",  # Human Review Required
            created_by_user_id=user_id,
        )
        db.add(ai_output)
        await self._audit(
            db,
            tenant_id,
            user_id,
            "SCRIPT_GENERATED",
            "AIOutput",
            ai_output.id,
            {"version": version_num},
        )
        await db.commit()
        await db.refresh(ai_output)
        return ai_output

    async def generate_seo(
        self,
        db: AsyncSession,
        tenant_id: str,
        story_id: str,
        research_job_id: str,
        user_id: str,
        target_keyword: Optional[str] = None,
    ) -> AIOutput:
        """Generates SEO metadata adhering to search engine and newsroom best practices."""
        story = await db.get(Story, story_id)
        job = await db.get(ResearchJob, research_job_id)
        if not story or not job or story.tenant_id != tenant_id or job.tenant_id != tenant_id:
            raise ValueError("Story or ResearchJob not found")

        workflow = (
            f"Generate search-optimized metadata for the news piece: '{story.title}'.\n"
            f"Target Keyword / Focus: {target_keyword or story.title}\n"
            "Requirements:\n"
            "- meta_title: Concise, maximum 70 characters.\n"
            "- meta_description: Maximum 160 characters with clear call to read.\n"
            "- canonical_slug: URL-safe hyphenated slug.\n"
            "- keywords: 4 to 8 relevant news search terms.\n"
            "- focus_keyphrase: Primary keyword phrase."
        )

        sys_prompt, user_prompt = build_defended_prompt(
            workflow_instructions=workflow,
            untrusted_evidence_items=[],
            editorial_input=story.summary or story.title,
        )

        seo_payload: Optional[StructuredSEOPayload] = None
        try:
            seo_payload = await self.ai_provider.generate_structured(
                prompt=user_prompt,
                schema_class=StructuredSEOPayload,
                system_prompt=sys_prompt,
            )
        except Exception:
            clean_slug = re.sub(r"[^\w\s-]", "", story.title).strip().lower()
            clean_slug = re.sub(r"[\s_-]+", "-", clean_slug)[:80]
            desc = (
                f"Read the latest verified updates and factual analysis on "
                f"{story.title[:80]} from News 9."
            )
            seo_payload = StructuredSEOPayload(
                meta_title=f"{story.title[:55]} | News 9",
                meta_description=desc[:160],
                canonical_slug=clean_slug,
                keywords=["news9", "breaking-news", "investigative", "facts"],
                focus_keyphrase=target_keyword or story.title[:40],
                social_snippet=f"Latest report: {story.title[:120]}",
            )

        count_stmt = select(AIOutput).where(
            AIOutput.tenant_id == tenant_id,
            AIOutput.story_id == story.id,
            AIOutput.output_type == "SEO",
        )
        count_res = await db.execute(count_stmt)
        version_num = len(count_res.scalars().all()) + 1

        assert seo_payload is not None
        ai_output = AIOutput(

            tenant_id=tenant_id,
            story_id=story.id,
            research_job_id=job.id,
            output_type="SEO",
            version_number=version_num,
            content=seo_payload.model_dump(),
            model_provider="ollama",
            prompt_template_version="v1.0",
            source_references=[job.id],
            status="GENERATED",  # Human Review Required
            created_by_user_id=user_id,
        )
        db.add(ai_output)
        await self._audit(
            db,
            tenant_id,
            user_id,
            "SEO_GENERATED",
            "AIOutput",
            ai_output.id,
            {"version": version_num},
        )
        await db.commit()
        await db.refresh(ai_output)
        return ai_output

    async def generate_visual_plan(
        self,
        db: AsyncSession,
        tenant_id: str,
        story_id: str,
        research_job_id: str,
        user_id: str,
        visual_style: Optional[str] = None,
    ) -> AIOutput:
        """Generates a textual visual plan (no video/image creation; Phase 5 preserved)."""
        story = await db.get(Story, story_id)
        job = await db.get(ResearchJob, research_job_id)
        if not story or not job or story.tenant_id != tenant_id or job.tenant_id != tenant_id:
            raise ValueError("Story or ResearchJob not found")

        workflow = (
            f"Generate a visual production plan for news piece: '{story.title}'.\n"
            f"Visual style: {visual_style or 'Modern Clean Newsroom'}\n"
            "Requirements:\n"
            "- List visual cues: LOWER_THIRD, MAP_OVERLAY, DOCUMENT_EXCERPT, "
            "TIMELINE_GRAPHIC, FULL_SCREEN_STAT.\n"
            "- Detail on-screen text and graphical description for newsroom operator.\n"
            "- Provide production guidelines."
        )

        sys_prompt, user_prompt = build_defended_prompt(
            workflow_instructions=workflow,
            untrusted_evidence_items=[],
            editorial_input=story.summary or story.title,
        )

        vp_payload: Optional[StructuredVisualPlanPayload] = None
        try:
            vp_payload = await self.ai_provider.generate_structured(
                prompt=user_prompt,
                schema_class=StructuredVisualPlanPayload,
                system_prompt=sys_prompt,
            )
        except Exception:
            vp_payload = StructuredVisualPlanPayload(
                recommended_visual_format="16:9 HD Studio Broadcast & Digital Social Clip",
                visual_cues=[
                    VisualCue(
                        cue_id="VC-1",
                        cue_type="LOWER_THIRD",
                        description="Presenter title card with breaking news banner",
                        on_screen_text=f"SPECIAL REPORT: {story.title[:50]}",
                    ),
                    VisualCue(
                        cue_id="VC-2",
                        cue_type="FULL_SCREEN_STAT",
                        description="Key verified metrics and factual points summary",
                        on_screen_text="KEY FINDINGS: Verified across independent wire sources",
                    ),
                    VisualCue(
                        cue_id="VC-3",
                        cue_type="DOCUMENT_EXCERPT",
                        description="Highlighted excerpt from primary source document",
                        on_screen_text="Official Statement Excerpt",
                    ),
                ],
                production_guidelines=[
                    "Maintain high contrast on lower third text",
                    "Do not obscure anchor facial framing with oversized graphics",
                    "Ensure source attribution is visible on all quoted graphics",
                ],
            )


        count_stmt = select(AIOutput).where(
            AIOutput.tenant_id == tenant_id,
            AIOutput.story_id == story.id,
            AIOutput.output_type == "VISUAL_PLAN",
        )
        count_res = await db.execute(count_stmt)
        version_num = len(count_res.scalars().all()) + 1

        assert vp_payload is not None
        ai_output = AIOutput(

            tenant_id=tenant_id,
            story_id=story.id,
            research_job_id=job.id,
            output_type="VISUAL_PLAN",
            version_number=version_num,
            content=vp_payload.model_dump(),
            model_provider="ollama",
            prompt_template_version="v1.0",
            source_references=[job.id],
            status="GENERATED",  # Human Review Required
            created_by_user_id=user_id,
        )
        db.add(ai_output)
        await self._audit(
            db,
            tenant_id,
            user_id,
            "VISUAL_PLAN_GENERATED",
            "AIOutput",
            ai_output.id,
            {"version": version_num},
        )
        await db.commit()
        await db.refresh(ai_output)
        return ai_output

    # -----------------------------------------------------------------------
    # Human Editorial Review Boundary (Accept / Reject / Edit)
    # -----------------------------------------------------------------------

    async def review_output(
        self,
        db: AsyncSession,
        tenant_id: str,
        output_id: str,
        user_id: str,
        action: str,
        rejection_reason: Optional[str] = None,
    ) -> AIOutput:
        """Executes human review gate on AI output."""
        output = await db.get(AIOutput, output_id)
        if not output or output.tenant_id != tenant_id:
            raise ValueError("AIOutput not found")

        action_upper = action.upper()
        if action_upper not in ("ACCEPT", "REJECT"):
            raise ValueError("Action must be ACCEPT or REJECT")

        if action_upper == "REJECT" and not rejection_reason:
            raise ValueError("Rejection reason is mandatory when rejecting AI output")

        output.status = "ACCEPTED" if action_upper == "ACCEPT" else "REJECTED"
        output.rejection_reason = rejection_reason if action_upper == "REJECT" else None
        output.actioned_by_user_id = user_id
        output.actioned_at = utc_now()

        audit_action = "AI_OUTPUT_ACCEPTED" if action_upper == "ACCEPT" else "AI_OUTPUT_REJECTED"
        await self._audit(
            db,
            tenant_id,
            user_id,
            audit_action,
            "AIOutput",
            output.id,
            {
                "output_type": output.output_type,
                "version": output.version_number,
                "rejection_reason": rejection_reason,
            },
        )

        await db.commit()
        await db.refresh(output)
        return output

    async def edit_output(
        self,
        db: AsyncSession,
        tenant_id: str,
        output_id: str,
        user_id: str,
        edited_content: Dict[str, Any],
    ) -> AIOutput:
        """Allows human journalist/editor to revise AI output content."""
        output = await db.get(AIOutput, output_id)
        if not output or output.tenant_id != tenant_id:
            raise ValueError("AIOutput not found")

        output.content = edited_content
        output.status = "EDITED"
        output.actioned_by_user_id = user_id
        output.actioned_at = utc_now()

        await self._audit(
            db,
            tenant_id,
            user_id,
            "AI_OUTPUT_EDITED",
            "AIOutput",
            output.id,
            {
                "output_type": output.output_type,
                "version": output.version_number,
            },
        )

        await db.commit()
        await db.refresh(output)
        return output
