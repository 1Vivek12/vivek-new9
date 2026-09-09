"""Schemas package."""

from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
)
from app.schemas.category import CategoryCreate, CategoryResponse
from app.schemas.source import SourceCreate as StorySourceCreate
from app.schemas.source import SourceResponse as StorySourceResponse
from app.schemas.story import (
    StoryCreate,
    StoryDetailResponse,
    StoryResponse,
    StoryStatusTransitionRequest,
    StoryUpdate,
)
from app.schemas.trend import (
    OpportunityConvertRequest,
    OpportunityResponse,
    SimilarStoryGroupDetailResponse,
    SimilarStoryGroupResponse,
    SourceCreate,
    SourceItemResponse,
    SourceResponse,
    SourceUpdate,
    TrendSearchRequest,
    TrendSearchResponse,
)
from app.schemas.version import VersionCreate, VersionResponse

__all__ = [
    "AssignmentCreate",
    "AssignmentUpdate",
    "AssignmentResponse",
    "CategoryCreate",
    "CategoryResponse",
    "StoryCreate",
    "StoryUpdate",
    "StoryResponse",
    "StoryDetailResponse",
    "StoryStatusTransitionRequest",
    "StorySourceCreate",
    "StorySourceResponse",
    "VersionCreate",
    "VersionResponse",
    "SourceCreate",
    "SourceUpdate",
    "SourceResponse",
    "SourceItemResponse",
    "SimilarStoryGroupResponse",
    "SimilarStoryGroupDetailResponse",
    "OpportunityResponse",
    "OpportunityConvertRequest",
    "TrendSearchRequest",
    "TrendSearchResponse",
]
