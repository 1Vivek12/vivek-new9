"""Pydantic schemas for Phase 5 Media & Video Production."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MediaRightsMetadata(BaseModel):
    """Rights and copyright attribution metadata."""

    rights_type: str = Field(
        default="UNKNOWN",
        description="OWNED, LICENSED, USER_PROVIDED, RESTRICTED, UNKNOWN",
    )
    license_details: Optional[str] = Field(default=None, max_length=500)
    attribution: Optional[str] = Field(default=None, max_length=255)
    editorial_notes: Optional[str] = Field(default=None, max_length=500)
    reuse_permitted: bool = Field(default=False)
    derivative_approval_status: str = Field(
        default="PENDING_REVIEW",
        description="PENDING_REVIEW, APPROVED, BLOCKED",
    )


class MediaAssetResponse(BaseModel):
    """Schema representing an ingested or processed media asset."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    story_id: Optional[str] = None
    uploaded_by_user_id: str
    filename: str
    original_filename: str
    media_type: str
    mime_type: str
    file_size: int
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    frame_rate: Optional[float] = None
    codec: Optional[str] = None
    container: Optional[str] = None
    checksum: str
    storage_key: str
    status: str
    rights_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class MediaDerivativeResponse(BaseModel):
    """Schema representing generated media derivatives (e.g. 9:16 vertical, audio extract)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    source_media_id: str
    derivative_type: str
    storage_key: str
    mime_type: str
    file_size: int
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    checksum: str
    processing_status: str
    metadata_payload: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CreateDerivativeRequest(BaseModel):
    """Request payload for creating a media derivative."""

    derivative_type: str = Field(default="VERTICAL_9_16", description="VERTICAL_9_16, PROXY, AUDIO")


class MediaProcessingJobResponse(BaseModel):
    """Schema representing an asynchronous media processing task."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    media_asset_id: str
    job_type: str
    status: str
    attempts: int
    max_attempts: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_code: Optional[str] = None
    safe_error_message: Optional[str] = None
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime


class TranscriptSegmentResponse(BaseModel):
    """Schema for individual timestamped dialogue segments."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    transcript_id: str
    sequence: int
    start_time: float
    end_time: float
    text: str
    speaker_label: str
    confidence: float
    created_at: datetime


class TranscriptResponse(BaseModel):
    """Schema for full media transcript."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    media_asset_id: str
    language: str
    model_provider: str
    model_version: Optional[str] = None
    duration: float
    status: str
    full_text: str
    confidence_score: float
    created_at: datetime
    segments: List[TranscriptSegmentResponse] = Field(default_factory=list)


class SceneResponse(BaseModel):
    """Schema for detected visual shot boundary."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    media_asset_id: str
    sequence: int
    start_time: float
    end_time: float
    keyframe_storage_key: Optional[str] = None
    scene_label: str
    confidence: float
    created_at: datetime


class OCRResultResponse(BaseModel):
    """Schema for machine-extracted on-screen text."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    media_asset_id: str
    timestamp: float
    extracted_text: str
    confidence: float
    bounding_box: Optional[Dict[str, Any]] = None
    source_frame_key: Optional[str] = None
    created_at: datetime


class ClipCandidateResponse(BaseModel):
    """Schema for AI / editorial clip candidate moments."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    media_asset_id: str
    title: str
    start_time: float
    end_time: float
    duration: float
    category: str
    reason: str
    suggested_aspect_ratio: str
    confidence: float
    status: str
    actioned_by_user_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SubtitleTrackResponse(BaseModel):
    """Schema for timed text subtitle tracks."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    media_asset_id: str
    language: str
    format: str
    storage_key: str
    content: str
    status: str
    generated_by: str
    created_at: datetime
    updated_at: datetime


class VisualAssetResponse(BaseModel):
    """Schema for extracted keyframes and thumbnail concept cards."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    media_asset_id: str
    asset_type: str
    timestamp: Optional[float] = None
    storage_key: Optional[str] = None
    headline_text: Optional[str] = None
    visual_concept_description: str
    status: str
    actioned_by_user_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ReviewActionRequest(BaseModel):
    """Editorial action payload for clip candidates or visual assets."""

    action: str = Field(description="ACCEPT or REJECT")
    rejection_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Mandatory if action is REJECT",
    )


class DownloadTokenResponse(BaseModel):
    """Signed short-lived download token response for media streaming."""

    download_token: str
    expires_in_seconds: int = 900
    stream_url: str
