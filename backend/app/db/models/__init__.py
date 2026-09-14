"""ORM Models registry."""

from app.db.base import Base
from app.db.models.assignment import Assignment
from app.db.models.audit import AuditLog
from app.db.models.category import Category
from app.db.models.media import (
    ClipCandidate,
    MediaAsset,
    MediaDerivative,
    MediaProcessingJob,
    OCRResult,
    Scene,
    SubtitleTrack,
    Transcript,
    TranscriptSegment,
    VisualAsset,
)
from app.db.models.membership import TenantMembership
from app.db.models.publishing import (
    AccountCredential,
    ConnectedAccount,
    OAuthState,
    PlatformPayload,
    PublishedItem,
    PublishingApprovalEvent,
    PublishingAttempt,
    PublishingDestination,
    PublishingJob,
    PublishingPackage,
    WebhookEvent,
)
from app.db.models.research import (
    AIContentPlan,
    AIOutput,
    ResearchBrief,
    ResearchClaim,
    ResearchEvidence,
    ResearchJob,
)
from app.db.models.source import StorySource
from app.db.models.source_registry import Source
from app.db.models.story import Story
from app.db.models.tenant import Tenant
from app.db.models.trend import ContentOpportunity, SimilarStoryGroup, SourceItem
from app.db.models.user import User
from app.db.models.version import StoryVersion

__all__ = [
    "Base",
    "Tenant",
    "User",
    "TenantMembership",
    "AuditLog",
    "Category",
    "Assignment",
    "Story",
    "StorySource",
    "StoryVersion",
    "Source",
    "SourceItem",
    "SimilarStoryGroup",
    "ContentOpportunity",
    "ResearchJob",
    "ResearchEvidence",
    "ResearchClaim",
    "ResearchBrief",
    "AIContentPlan",
    "AIOutput",
    "MediaAsset",
    "MediaDerivative",
    "MediaProcessingJob",
    "Transcript",
    "TranscriptSegment",
    "Scene",
    "OCRResult",
    "ClipCandidate",
    "SubtitleTrack",
    "VisualAsset",
    "PublishingDestination",
    "ConnectedAccount",
    "AccountCredential",
    "OAuthState",
    "PublishingPackage",
    "PlatformPayload",
    "PublishingApprovalEvent",
    "PublishingJob",
    "PublishingAttempt",
    "PublishedItem",
    "WebhookEvent",
]
