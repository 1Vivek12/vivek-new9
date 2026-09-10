"""Phase 5 Media & Video Production domain models."""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MediaAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Core media asset representing raw ingested or produced newsroom video/audio/images."""

    __tablename__ = "media_assets"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    story_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("stories.id", ondelete="SET NULL"), index=True, nullable=True
    )
    uploaded_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(32), nullable=False)  # VIDEO, AUDIO, IMAGE
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    frame_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    codec: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    container: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    checksum: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # SHA-256
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)

    # Discrete states: UPLOADED -> VALIDATING -> VALID -> METADATA_EXTRACTED ->
    # PROCESSING -> READY / PARTIAL_READY / FAILED / QUARANTINED
    status: Mapped[str] = mapped_column(String(32), default="UPLOADED", index=True, nullable=False)

    # Rights metadata: {rights_type, license_details, attribution, reuse_permitted}
    rights_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    story = relationship("Story")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_user_id])
    derivatives = relationship(
        "MediaDerivative", back_populates="source_media", cascade="all, delete-orphan"
    )
    jobs = relationship(
        "MediaProcessingJob", back_populates="media_asset", cascade="all, delete-orphan"
    )
    transcripts = relationship(
        "Transcript", back_populates="media_asset", cascade="all, delete-orphan"
    )
    scenes = relationship(
        "Scene", back_populates="media_asset", cascade="all, delete-orphan"
    )
    ocr_results = relationship(
        "OCRResult", back_populates="media_asset", cascade="all, delete-orphan"
    )
    clip_candidates = relationship(
        "ClipCandidate", back_populates="media_asset", cascade="all, delete-orphan"
    )
    subtitles = relationship(
        "SubtitleTrack", back_populates="media_asset", cascade="all, delete-orphan"
    )
    visual_assets = relationship(
        "VisualAsset", back_populates="media_asset", cascade="all, delete-orphan"
    )


class MediaDerivative(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Derived media representations: proxies, vertical 9:16, audio extracts, keyframes, clips."""

    __tablename__ = "media_derivatives"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_media_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), index=True, nullable=False
    )

    derivative_type: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(32), default="READY", index=True, nullable=False
    )  # READY, FAILED, PENDING
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    source_media = relationship("MediaAsset", back_populates="derivatives")


class MediaProcessingJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks discrete media processing tasks and state transitions."""

    __tablename__ = "media_processing_jobs"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), index=True, nullable=False
    )

    job_type: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default="QUEUED", index=True, nullable=False
    )  # QUEUED, RUNNING, COMPLETED, FAILED, TOOL_UNAVAILABLE, CANCELLED

    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    safe_error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    # Relationships
    tenant = relationship("Tenant")
    media_asset = relationship("MediaAsset", back_populates="jobs")
    created_by = relationship("User", foreign_keys=[created_by_user_id])


class Transcript(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Transcript container generated by local transcription."""

    __tablename__ = "transcripts"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), index=True, nullable=False
    )

    language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    model_provider: Mapped[str] = mapped_column(String(64), default="whisper_local", nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    duration: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="COMPLETED", nullable=False
    )  # COMPLETED, FAILED, TOOL_UNAVAILABLE
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.9, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    media_asset = relationship("MediaAsset", back_populates="transcripts")
    segments = relationship(
        "TranscriptSegment", back_populates="transcript", cascade="all, delete-orphan"
    )


class TranscriptSegment(Base, UUIDPrimaryKeyMixin):
    """Timestamped sentence or utterance segment with honest speaker identity."""

    __tablename__ = "transcript_segments"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    transcript_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("transcripts.id", ondelete="CASCADE"), index=True, nullable=False
    )

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    speaker_label: Mapped[str] = mapped_column(String(64), default="Speaker 1", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.9, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    transcript = relationship("Transcript", back_populates="segments")


class Scene(Base, UUIDPrimaryKeyMixin):
    """Detected visual shot boundary with keyframe reference."""

    __tablename__ = "scenes"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), index=True, nullable=False
    )

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    keyframe_storage_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    scene_label: Mapped[str] = mapped_column(String(128), default="Scene Segment", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    media_asset = relationship("MediaAsset", back_populates="scenes")


class OCRResult(Base, UUIDPrimaryKeyMixin):
    """Machine-extracted on-screen text from media frames."""

    __tablename__ = "ocr_results"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), index=True, nullable=False
    )

    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    extracted_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    bounding_box: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    source_frame_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    media_asset = relationship("MediaAsset", back_populates="ocr_results")


class ClipCandidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Important moment or short-form clip candidate for human editorial review."""

    __tablename__ = "clip_candidates"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), index=True, nullable=False
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(
        String(64), default="SHORT_CANDIDATE", nullable=False
    )  # QUOTE, IMPORTANT_EVENT, KEY_STATEMENT, VISUAL_MOMENT, SHORT_CANDIDATE, EDITORIAL_HIGHLIGHT
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_aspect_ratio: Mapped[str] = mapped_column(String(16), default="9:16", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)

    # Human review gate: SUGGESTED -> ACCEPTED / REJECTED
    status: Mapped[str] = mapped_column(String(32), default="SUGGESTED", index=True, nullable=False)
    actioned_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    media_asset = relationship("MediaAsset", back_populates="clip_candidates")
    actioned_by = relationship("User", foreign_keys=[actioned_by_user_id])


class SubtitleTrack(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Timed text subtitle/caption track for broadcast or digital presentation."""

    __tablename__ = "subtitle_tracks"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), index=True, nullable=False
    )

    language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    format: Mapped[str] = mapped_column(String(16), default="SRT", nullable=False)  # SRT, VTT
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="GENERATED", nullable=False
    )  # GENERATED, EDITED, APPROVED
    generated_by: Mapped[str] = mapped_column(
        String(64), default="TRANSCRIPT_AUTOMATION", nullable=False
    )

    # Relationships
    media_asset = relationship("MediaAsset", back_populates="subtitles")


class VisualAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Visual thumbnail candidate or extracted keyframe card for editorial review."""

    __tablename__ = "visual_assets"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), index=True, nullable=False
    )

    asset_type: Mapped[str] = mapped_column(
        String(64), default="KEYFRAME", nullable=False
    )  # KEYFRAME, THUMBNAIL_CANDIDATE, CONCEPT_CARD
    timestamp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    storage_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    headline_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    visual_concept_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Human review gate: CANDIDATE -> ACCEPTED / REJECTED
    status: Mapped[str] = mapped_column(String(32), default="CANDIDATE", index=True, nullable=False)
    actioned_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    media_asset = relationship("MediaAsset", back_populates="visual_assets")
    actioned_by = relationship("User", foreign_keys=[actioned_by_user_id])
