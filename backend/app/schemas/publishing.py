"""Phase 6 Publishing & Distribution Pydantic schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DestinationResponse(BaseModel):
    id: str
    tenant_id: str
    destination_type: str
    display_name: str
    is_active: bool
    config_payload: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConnectedAccountResponse(BaseModel):
    id: str
    tenant_id: str
    destination_id: str
    account_type: str
    platform_account_id: str
    account_name: str
    account_metadata: Dict[str, Any]
    connection_status: str
    last_health_check_at: Optional[datetime]
    connected_by_user_id: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlatformPayloadResponse(BaseModel):
    id: str
    tenant_id: str
    package_id: str
    destination_type: str
    account_id: str
    adapted_title: str
    adapted_description: str
    adapted_caption: str
    target_aspect_ratio: str
    selected_derivative_id: Optional[str]
    selected_thumbnail_id: Optional[str]
    custom_metadata: Dict[str, Any]
    validation_status: str
    validation_errors: List[str]

    model_config = ConfigDict(from_attributes=True)


class UpdatePlatformPayloadRequest(BaseModel):
    adapted_title: Optional[str] = None
    adapted_description: Optional[str] = None
    adapted_caption: Optional[str] = None
    target_aspect_ratio: Optional[str] = None
    selected_derivative_id: Optional[str] = None
    selected_thumbnail_id: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None


class CreatePublishingPackageRequest(BaseModel):
    story_id: str
    story_version_id: str
    destination_types: List[str] = Field(min_length=1)
    account_ids: Optional[List[str]] = None
    canonical_title: Optional[str] = None
    canonical_description: Optional[str] = None
    canonical_caption: Optional[str] = None
    tags: Optional[List[str]] = None
    primary_media_asset_id: Optional[str] = None
    primary_derivative_id: Optional[str] = None
    visual_asset_id: Optional[str] = None
    subtitle_track_id: Optional[str] = None


class PublishingApprovalRequest(BaseModel):
    action: str = Field(pattern="^(APPROVE|REJECT)$")
    rejection_reason: Optional[str] = None


class PublishingApprovalEventResponse(BaseModel):
    id: str
    tenant_id: str
    package_id: str
    event_type: str
    decided_by_user_id: str
    decided_at: datetime
    publication_manifest_hash: str
    manifest_snapshot: Dict[str, Any]
    reason: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublishingAttemptResponse(BaseModel):
    id: str
    tenant_id: str
    job_id: str
    attempt_number: int
    started_at: datetime
    duration_ms: int
    http_status_code: Optional[int]
    platform_error_code: Optional[str]
    sanitized_error_message: Optional[str]
    outcome: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublishingJobResponse(BaseModel):
    id: str
    tenant_id: str
    package_id: str
    account_id: str
    publication_idempotency_key: str
    job_status: str
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    attempts: int
    max_attempts: int
    last_error_code: Optional[str]
    safe_error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublishedItemResponse(BaseModel):
    id: str
    tenant_id: str
    package_id: str
    account_id: str
    destination_type: str
    external_item_id: str
    external_url: str
    published_at: datetime
    visibility: str
    platform_state: str
    last_checked_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublishingPackageResponse(BaseModel):
    id: str
    tenant_id: str
    story_id: str
    story_version_id: str
    primary_media_asset_id: Optional[str]
    primary_derivative_id: Optional[str]
    visual_asset_id: Optional[str]
    subtitle_track_id: Optional[str]
    canonical_title: str
    canonical_description: str
    canonical_caption: Optional[str]
    tags: List[str]
    status: str
    current_approval_id: Optional[str]
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    payloads: List[PlatformPayloadResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ValidationResultResponse(BaseModel):
    package_id: str
    is_valid: bool
    manifest_hash: Optional[str]
    validation_errors: List[str]
    payload_validations: Dict[str, List[str]]


class SchedulePublishRequest(BaseModel):
    scheduled_at: datetime


class ExternalMediaDeliveryTokenResponse(BaseModel):
    delivery_url: str
    expires_in_seconds: int
    expires_at: datetime
