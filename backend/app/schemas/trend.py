"""Pydantic schemas for Trend Radar, Source Registry, and Content Opportunities."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# -----------------------------------------------------------------------------
# Source Registry Schemas
# -----------------------------------------------------------------------------

class SourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    source_type: str = Field(default="RSS")
    feed_url: Optional[str] = Field(default=None, max_length=2048)
    website_url: Optional[str] = Field(default=None, max_length=2048)
    publisher_name: Optional[str] = Field(default=None, max_length=255)
    reliability_score: Optional[float] = Field(default=70.0, ge=0.0, le=100.0)
    trust_level: str = Field(default="MEDIUM")
    jurisdiction: Optional[str] = Field(default=None, max_length=100)
    language: str = Field(default="en", max_length=10)
    is_active: bool = True
    polling_interval_minutes: int = Field(default=60, ge=5, le=1440)
    rights_metadata: Dict[str, Any] = Field(
        default_factory=lambda: {
            "rights_type": "public_information",
            "reuse_permitted": False,
            "citation_required": True,
        }
    )


class SourceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    source_type: Optional[str] = None
    feed_url: Optional[str] = Field(default=None, max_length=2048)
    website_url: Optional[str] = Field(default=None, max_length=2048)
    publisher_name: Optional[str] = Field(default=None, max_length=255)
    reliability_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    trust_level: Optional[str] = None
    jurisdiction: Optional[str] = None
    language: Optional[str] = None
    is_active: Optional[bool] = None
    polling_interval_minutes: Optional[int] = Field(default=None, ge=5, le=1440)
    rights_metadata: Optional[Dict[str, Any]] = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    source_type: str
    feed_url: Optional[str] = None
    website_url: Optional[str] = None
    publisher_name: Optional[str] = None
    reliability_score: Optional[float] = None
    trust_level: str
    jurisdiction: Optional[str] = None
    language: str
    is_active: bool
    polling_interval_minutes: int
    rights_metadata: Dict[str, Any]
    last_fetched_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    failure_count: int
    last_error_message: Optional[str] = None
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime


# -----------------------------------------------------------------------------
# Source Item Schemas
# -----------------------------------------------------------------------------

class SourceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    source_id: str
    similar_story_group_id: Optional[str] = None
    external_id: Optional[str] = None
    canonical_url: str
    title: str
    summary: Optional[str] = None
    publisher: Optional[str] = None
    published_at: Optional[datetime] = None
    fetched_at: datetime
    language: str
    reliability_score: Optional[float] = None
    rights_metadata: Dict[str, Any]
    raw_metadata: Dict[str, Any]
    fingerprint: str
    created_at: datetime
    updated_at: datetime


# -----------------------------------------------------------------------------
# Similar Story Group Schemas
# -----------------------------------------------------------------------------

class SimilarStoryGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    representative_title: str
    topic_keywords: List[str]
    source_count: int
    independent_publisher_count: int
    strongest_source_reliability: float
    first_seen_at: datetime
    latest_seen_at: datetime
    trend_score: float
    created_at: datetime
    updated_at: datetime


class SimilarStoryGroupDetailResponse(SimilarStoryGroupResponse):
    items: Optional[List[SourceItemResponse]] = None


# -----------------------------------------------------------------------------
# Content Opportunity Schemas
# -----------------------------------------------------------------------------

class OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    similar_story_group_id: Optional[str] = None
    category_id: Optional[str] = None
    topic: str
    headline: str
    summary: str
    trend_score: float
    confidence_score: float
    source_count: int
    publisher_count: int
    urgency: str
    status: str
    risk_indicators: List[str]
    score_explanation: Dict[str, Any]
    converted_story_id: Optional[str] = None
    actioned_by_user_id: Optional[str] = None
    actioned_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    related_items: Optional[List[SourceItemResponse]] = None


class OpportunityConvertRequest(BaseModel):
    category_id: Optional[str] = None
    editorial_owner_id: Optional[str] = None
    priority: str = Field(default="NORMAL")


# -----------------------------------------------------------------------------
# Trend Topic Search Schemas
# -----------------------------------------------------------------------------

class TrendSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = None
    language: Optional[str] = None
    time_window_hours: int = Field(default=48, ge=1, le=168)
    source_type: Optional[str] = None
    min_reliability: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    jurisdiction: Optional[str] = None


class TrendSearchResponse(BaseModel):
    query: str
    total_matching_items: int
    opportunities: List[OpportunityResponse]
    groups: List[SimilarStoryGroupResponse]
    items: List[SourceItemResponse]
