"""Pydantic schemas for Phase 4 AI Research & Content Intelligence."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------

# Structured AI Generation Schemas (Pydantic models used with generate_structured)
# ---------------------------------------------------------------------------


class StructuredClaim(BaseModel):
    claim_text: str = Field(..., max_length=500)
    claim_type: str = Field("FACT", description="FACT, STATISTIC, QUOTE, ATTRIBUTION, ALLEGATION")
    confidence_score: float = Field(0.8, ge=0.0, le=1.0)
    status: str = Field(
        "NEEDS_REVIEW", description="SUPPORTED, CONFLICTING, INSUFFICIENT, NEEDS_REVIEW"
    )
    supporting_evidence_indices: List[int] = Field(default_factory=list)
    contradicting_evidence_indices: List[int] = Field(default_factory=list)
    verification_notes: Optional[str] = Field(None, max_length=500)


class TimelineEvent(BaseModel):
    timestamp_or_period: str
    description: str


class StructuredBriefPayload(BaseModel):
    what_happened: str
    who_involved: List[str] = Field(default_factory=list)
    when_timeline: List[TimelineEvent] = Field(default_factory=list)
    where_locations: List[str] = Field(default_factory=list)
    why_causes: Optional[str] = None
    confirmed_facts: List[str] = Field(default_factory=list)
    disputed_facts: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    key_entities: List[str] = Field(default_factory=list)
    source_confidence: float = Field(0.8, ge=0.0, le=1.0)
    editorial_warnings: List[str] = Field(default_factory=list)
    suggested_angles: List[str] = Field(default_factory=list)
    extracted_claims: List[StructuredClaim] = Field(default_factory=list)


class NarrativeSection(BaseModel):
    section_title: str
    key_points: List[str]
    suggested_duration_seconds: Optional[int] = None


class StructuredContentPlanPayload(BaseModel):
    proposed_angle: str = Field(..., max_length=255)
    target_audience: str = Field(..., max_length=255)
    key_message: str
    narrative_structure: List[NarrativeSection] = Field(default_factory=list)
    suggested_format: str = Field("DIGITAL_EXPLAINER", max_length=64)
    editorial_caveats: List[str] = Field(default_factory=list)
    confidence_score: float = Field(0.8, ge=0.0, le=1.0)


class HeadlineVariant(BaseModel):
    headline: str
    style_category: str = Field("DIRECT", description="DIRECT, ANALYTICAL, QUESTION, IMPACT")
    character_count: int
    clickbait_risk_score: float = Field(0.1, ge=0.0, le=1.0)
    evidence_basis: str


class StructuredHeadlinesPayload(BaseModel):
    headlines: List[HeadlineVariant] = Field(default_factory=list)
    summary_of_angles: Optional[str] = None


class ScriptSegment(BaseModel):
    segment_number: int
    segment_type: str = Field(
        "ANCHOR_INTRO",
        description="ANCHOR_INTRO, EVIDENCE_READ, REPORTER_STANDUP, GRAPHIC_VO, CLOSE",
    )
    speaker: str = Field("Anchor")
    spoken_text: str
    visual_cue: Optional[str] = None
    status_label: str = Field(
        "CONFIRMED_FACT", description="CONFIRMED_FACT, ATTRIBUTED_CLAIM, DEVELOPING"
    )


class StructuredScriptPayload(BaseModel):
    title: str
    estimated_duration_seconds: int
    segments: List[ScriptSegment] = Field(default_factory=list)
    compliance_notes: List[str] = Field(default_factory=list)


class StructuredSEOPayload(BaseModel):
    meta_title: str = Field(..., max_length=70)
    meta_description: str = Field(..., max_length=160)
    canonical_slug: str = Field(..., max_length=255)
    keywords: List[str] = Field(default_factory=list)
    focus_keyphrase: str
    social_snippet: Optional[str] = None


class VisualCue(BaseModel):
    cue_id: str
    cue_type: str = Field(
        "LOWER_THIRD",
        description=(
            "LOWER_THIRD, MAP_OVERLAY, DOCUMENT_EXCERPT, TIMELINE_GRAPHIC, FULL_SCREEN_STAT"
        ),
    )


    description: str
    on_screen_text: Optional[str] = None
    associated_evidence_id: Optional[str] = None


class StructuredVisualPlanPayload(BaseModel):
    recommended_visual_format: str
    visual_cues: List[VisualCue] = Field(default_factory=list)
    production_guidelines: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API Request & Response Schemas
# ---------------------------------------------------------------------------


class ResearchJobCreate(BaseModel):
    query_topic: Optional[str] = None
    opportunity_id: Optional[str] = None


class ResearchJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    story_id: str
    opportunity_id: Optional[str]
    query_topic: str
    status: str
    requested_by_user_id: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    failure_reason: Optional[str]
    created_at: datetime
    updated_at: datetime


class ResearchEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    research_job_id: str
    source_item_id: Optional[str]
    canonical_url: str
    publisher: Optional[str]
    title: str
    published_at: Optional[datetime]
    accessed_at: datetime
    evidence_snippet: str
    normalized_claim_summary: str
    source_reliability: Optional[float]
    confidence_score: float
    rights_metadata: Dict[str, Any]
    adversarial_instruction_flag: bool
    created_at: datetime


class ResearchClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    research_job_id: str
    claim_text: str
    claim_type: str
    confidence_score: float
    status: str
    supporting_evidence_ids: List[str]
    contradicting_evidence_ids: List[str]
    verification_notes: Optional[str]
    created_at: datetime


class ResearchBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    research_job_id: str
    story_id: str
    what_happened: str
    who_involved: List[str]
    when_timeline: List[Dict[str, Any]]
    where_locations: List[str]
    why_causes: Optional[str]
    confirmed_facts: List[str]
    disputed_facts: List[str]
    unknowns: List[str]
    key_entities: List[str]
    source_confidence: float
    editorial_warnings: List[str]
    suggested_angles: List[str]
    created_at: datetime


class AIContentPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    research_job_id: str
    story_id: str
    proposed_angle: str
    target_audience: str
    key_message: str
    narrative_structure: List[Dict[str, Any]]
    suggested_format: str
    editorial_caveats: List[str]
    confidence_score: float
    version_number: int
    created_at: datetime


class AIOutputResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    story_id: str
    research_job_id: Optional[str]
    output_type: str
    version_number: int
    content: Dict[str, Any]
    model_provider: str
    model_version: Optional[str]
    prompt_template_version: str
    source_references: List[str]
    status: str
    rejection_reason: Optional[str]
    actioned_by_user_id: Optional[str]
    actioned_at: Optional[datetime]
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime


class AIOutputActionRequest(BaseModel):
    action: str = Field(..., description="ACCEPT or REJECT")
    rejection_reason: Optional[str] = Field(None, max_length=500)


class AIOutputEditRequest(BaseModel):
    content: Dict[str, Any]


class ContentPlanGenerateRequest(BaseModel):
    editorial_angle: Optional[str] = None
    target_audience: Optional[str] = None


class HeadlinesGenerateRequest(BaseModel):
    count: int = Field(5, ge=1, le=10)
    focus: Optional[str] = None


class ScriptGenerateRequest(BaseModel):
    script_format: str = Field(
        "TV_NEWS_RUNDOWN", description="TV_NEWS_RUNDOWN, PODCAST_SUMMARY, VIDEO_EXPLAINER"
    )
    target_duration_seconds: int = Field(90, ge=30, le=600)


class SEOGenerateRequest(BaseModel):
    target_keyword: Optional[str] = None


class VisualPlanGenerateRequest(BaseModel):
    visual_style: Optional[str] = None
