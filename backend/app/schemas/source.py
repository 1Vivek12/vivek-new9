"""StorySource Pydantic schemas."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    url: Optional[str] = Field(default=None, max_length=2048)
    publisher_name: Optional[str] = Field(default=None, max_length=255)
    source_type: str = Field(default="OTHER")
    published_at: Optional[datetime] = None
    reliability_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    rights_metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    story_id: str
    title: str
    url: Optional[str] = None
    publisher_name: Optional[str] = None
    source_type: str
    published_at: Optional[datetime] = None
    accessed_at: datetime
    reliability_score: Optional[float] = None
    rights_metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
