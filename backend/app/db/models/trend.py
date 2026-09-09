"""Trend Radar models: SourceItem, SimilarStoryGroup, and ContentOpportunity."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class SourceItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Normalized ingested item from an external source."""

    __tablename__ = "source_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "fingerprint", name="uq_source_item_tenant_fingerprint"),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    similar_story_group_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("similar_story_groups.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    external_id: Mapped[Optional[str]] = mapped_column(String(512), index=True, nullable=True)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    reliability_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rights_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    raw_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    source = relationship("Source", back_populates="items")
    group = relationship("SimilarStoryGroup", back_populates="items")


class SimilarStoryGroup(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Cluster of related source items describing the same emerging event or topic."""

    __tablename__ = "similar_story_groups"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    representative_title: Mapped[str] = mapped_column(String(500), nullable=False)
    topic_keywords: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    source_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    independent_publisher_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    strongest_source_reliability: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    latest_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    trend_score: Mapped[float] = mapped_column(Float, default=0.0, index=True, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    items = relationship("SourceItem", back_populates="group")
    opportunities = relationship("ContentOpportunity", back_populates="group")


class ContentOpportunity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Editorial content opportunity derived from trend detection."""

    __tablename__ = "content_opportunities"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    similar_story_group_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("similar_story_groups.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    category_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    topic: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    trend_score: Mapped[float] = mapped_column(Float, default=0.0, index=True, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    publisher_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    urgency: Mapped[str] = mapped_column(
        String(32), default="NORMAL", nullable=False
    )  # LOW, NORMAL, HIGH, URGENT
    status: Mapped[str] = mapped_column(
        String(32), default="DISCOVERED", index=True, nullable=False
    )  # DISCOVERED, REVIEW_REQUIRED, ACCEPTED, REJECTED, CONVERTED_TO_STORY, EXPIRED

    risk_indicators: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    score_explanation: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Editorial conversion linkage
    converted_story_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("stories.id", ondelete="SET NULL"), nullable=True
    )
    actioned_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actioned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    group = relationship("SimilarStoryGroup", back_populates="opportunities")
    category = relationship("Category")
    converted_story = relationship("Story")
    actioned_by = relationship("User")
