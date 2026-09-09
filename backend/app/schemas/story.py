"""Story Pydantic schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assignment import AssignmentResponse
from app.schemas.category import CategoryResponse
from app.schemas.source import SourceResponse
from app.schemas.version import VersionResponse


class StoryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = Field(default=None, max_length=255)
    summary: Optional[str] = None
    category_id: Optional[str] = None
    assignment_id: Optional[str] = None
    priority: str = Field(default="NORMAL")


class StoryUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    summary: Optional[str] = None
    category_id: Optional[str] = None
    assignment_id: Optional[str] = None
    priority: Optional[str] = None
    editorial_owner_id: Optional[str] = None


class StoryStatusTransitionRequest(BaseModel):
    target_status: str = Field(...)
    rejection_reason: Optional[str] = None


class StoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    title: str
    slug: str
    summary: Optional[str] = None
    category_id: Optional[str] = None
    assignment_id: Optional[str] = None
    priority: str
    status: str
    editorial_owner_id: Optional[str] = None
    created_by_user_id: str
    updated_by_user_id: Optional[str] = None
    approved_by_user_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class StoryDetailResponse(StoryResponse):
    category: Optional[CategoryResponse] = None
    assignment: Optional[AssignmentResponse] = None
    sources: List[SourceResponse] = Field(default_factory=list)
    versions: List[VersionResponse] = Field(default_factory=list)
