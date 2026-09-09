"""StoryVersion Pydantic schemas."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class VersionCreate(BaseModel):
    headline: str = Field(..., min_length=1, max_length=255)
    body_payload: Dict[str, Any] = Field(default_factory=dict)
    body_text: Optional[str] = None
    change_summary: Optional[str] = Field(default=None, max_length=255)


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    story_id: str
    version_number: int
    headline: str
    body_payload: Dict[str, Any]
    body_text: Optional[str] = None
    change_summary: Optional[str] = None
    created_by_user_id: str
    created_at: datetime
