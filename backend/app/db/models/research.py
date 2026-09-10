"""Phase 4 AI Research & Content Intelligence models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class ResearchJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Asynchronous research orchestration job for an editorial story."""

    __tablename__ = "research_jobs"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    story_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("stories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    opportunity_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("content_opportunities.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    query_topic: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="QUEUED", index=True, nullable=False
    )  # QUEUED, RUNNING, COMPLETED, FAILED

    requested_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    story = relationship("Story")
    opportunity = relationship("ContentOpportunity")
    requested_by = relationship("User", foreign_keys=[requested_by_user_id])
    evidence_items = relationship(
        "ResearchEvidence", back_populates="research_job", cascade="all, delete-orphan"
    )
    claims = relationship(
        "ResearchClaim", back_populates="research_job", cascade="all, delete-orphan"
    )
    brief = relationship(
        "ResearchBrief", back_populates="research_job", uselist=False, cascade="all, delete-orphan"
    )
    content_plans = relationship(
        "AIContentPlan", back_populates="research_job", cascade="all, delete-orphan"
    )
    ai_outputs = relationship("AIOutput", back_populates="research_job")


class ResearchEvidence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Source evidence item attached to a research job.

    STRICT COPYRIGHT BOUNDARY:
    Full competitor articles or source pages must NOT be stored.
    Storage is bounded to a maximum 750-character snippet and
    a 500-character normalized factual claim summary.
    """

    __tablename__ = "research_evidence"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    research_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_item_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("source_items.id", ondelete="SET NULL"), index=True, nullable=True
    )

    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Strict storage boundaries (Max 750 chars excerpt, Max 500 chars claim summary)
    evidence_snippet: Mapped[str] = mapped_column(String(750), nullable=False)
    normalized_claim_summary: Mapped[str] = mapped_column(String(500), nullable=False)

    source_reliability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    rights_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Telemetry only - adversarial instruction detection does NOT mutate text
    adversarial_instruction_flag: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Relationships
    tenant = relationship("Tenant")
    research_job = relationship("ResearchJob", back_populates="evidence_items")
    source_item = relationship("SourceItem")


class ResearchClaim(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Factual proposition extracted and verified across evidence sources."""

    __tablename__ = "research_claims"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    research_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )

    claim_text: Mapped[str] = mapped_column(String(500), nullable=False)
    claim_type: Mapped[str] = mapped_column(
        String(32), default="FACT", nullable=False
    )  # FACT, STATISTIC, QUOTE, ATTRIBUTION, ALLEGATION

    confidence_score: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="NEEDS_REVIEW", nullable=False
    )  # SUPPORTED, CONFLICTING, INSUFFICIENT, NEEDS_REVIEW

    supporting_evidence_ids: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    contradicting_evidence_ids: Mapped[List[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    verification_notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    research_job = relationship("ResearchJob", back_populates="claims")


class ResearchBrief(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Structured 5W1H journalistic research brief synthesized from evidence."""

    __tablename__ = "research_briefs"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    research_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    story_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("stories.id", ondelete="CASCADE"), index=True, nullable=False
    )

    what_happened: Mapped[str] = mapped_column(Text, nullable=False)
    who_involved: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    when_timeline: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    where_locations: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    why_causes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    confirmed_facts: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    disputed_facts: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    unknowns: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    key_entities: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    source_confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    editorial_warnings: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    suggested_angles: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    research_job = relationship("ResearchJob", back_populates="brief")
    story = relationship("Story")


class AIContentPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Editorial content plan proposed by AI for human journalist review."""

    __tablename__ = "ai_content_plans"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    research_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    story_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("stories.id", ondelete="CASCADE"), index=True, nullable=False
    )

    proposed_angle: Mapped[str] = mapped_column(String(255), nullable=False)
    target_audience: Mapped[str] = mapped_column(String(255), nullable=False)
    key_message: Mapped[str] = mapped_column(Text, nullable=False)
    narrative_structure: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    suggested_format: Mapped[str] = mapped_column(
        String(64), default="DIGITAL_EXPLAINER", nullable=False
    )

    editorial_caveats: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    research_job = relationship("ResearchJob", back_populates="content_plans")
    story = relationship("Story")


class AIOutput(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable versioned AI output asset requiring human editorial review."""

    __tablename__ = "ai_outputs"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    story_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("stories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    research_job_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("research_jobs.id", ondelete="SET NULL"), index=True, nullable=True
    )

    output_type: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # HEADLINE, SCRIPT, SEO, VISUAL_PLAN, CONTENT_PLAN, RESEARCH_BRIEF
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    model_provider: Mapped[str] = mapped_column(String(64), default="ollama", nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    prompt_template_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    source_references: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    # Human Editorial Review Boundary
    status: Mapped[str] = mapped_column(
        String(32), default="GENERATED", index=True, nullable=False
    )  # GENERATED, REVIEW_REQUIRED, ACCEPTED, REJECTED, EDITED
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    actioned_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actioned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    # Relationships
    tenant = relationship("Tenant")
    story = relationship("Story")
    research_job = relationship("ResearchJob", back_populates="ai_outputs")
    actioned_by = relationship("User", foreign_keys=[actioned_by_user_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])
