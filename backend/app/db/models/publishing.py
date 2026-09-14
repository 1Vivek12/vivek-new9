"""Phase 6 Publishing & Distribution domain models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class DestinationType(str, Enum):
    """Supported publishing destination types."""

    YOUTUBE = "YOUTUBE"
    FACEBOOK = "FACEBOOK"
    INSTAGRAM = "INSTAGRAM"
    WHATSAPP = "WHATSAPP"
    WEBSITE = "WEBSITE"


class PublishingDestination(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Enabled publishing channel type per tenant (YouTube, Facebook, Instagram, etc.)."""

    __tablename__ = "publishing_destinations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "destination_type", name="uq_publishing_dest_tenant_type"),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    destination_type: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # YOUTUBE, FACEBOOK, INSTAGRAM, WHATSAPP, WEBSITE
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    accounts = relationship(
        "ConnectedAccount", back_populates="destination", cascade="all, delete-orphan"
    )


class ConnectedAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Connected external channel/page identity supporting controlled resurrection on reconnect."""

    __tablename__ = "connected_accounts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "destination_id",
            "platform_account_id",
            name="uq_connected_account_identity",
        ),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    destination_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("publishing_destinations.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    account_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # CHANNEL, PAGE, BUSINESS_ACCOUNT
    platform_account_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # CONNECTED, EXPIRED, REVOKED, ERROR
    connection_status: Mapped[str] = mapped_column(
        String(32), default="CONNECTED", index=True, nullable=False
    )
    last_health_check_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    connected_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    # Controlled resurrection flag: disconnected accounts are marked is_deleted=True
    # without deleting history
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    destination = relationship("PublishingDestination", back_populates="accounts")
    connected_by = relationship("User", foreign_keys=[connected_by_user_id])
    credential = relationship(
        "AccountCredential", back_populates="account", uselist=False, cascade="all, delete-orphan"
    )
    published_items = relationship("PublishedItem", back_populates="account")


class AccountCredential(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """AES-256-GCM encrypted tokens and secrets bound to tenant and account AAD."""

    __tablename__ = "account_credentials"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("connected_accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    access_token_nonce: Mapped[str] = mapped_column(String(32), nullable=False)
    encrypted_refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token_nonce: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    token_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    account = relationship("ConnectedAccount", back_populates="credential")


class OAuthState(Base):
    """Server-side ephemeral OAuth transaction state enforcing single-use and PKCE verification."""

    __tablename__ = "oauth_states"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )  # cryptographically secure random token
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    initiating_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    destination_type: Mapped[str] = mapped_column(String(32), nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class PublishingPackage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Canonical editorial package ready for multi-destination distribution."""

    __tablename__ = "publishing_packages"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    story_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("stories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    story_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("story_versions.id", ondelete="RESTRICT"), index=True, nullable=False
    )

    primary_media_asset_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True
    )
    primary_derivative_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("media_derivatives.id", ondelete="SET NULL"), nullable=True
    )
    visual_asset_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("visual_assets.id", ondelete="SET NULL"), nullable=True
    )
    subtitle_track_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("subtitle_tracks.id", ondelete="SET NULL"), nullable=True
    )

    canonical_title: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_description: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    # DRAFT, VALIDATING, READY_FOR_APPROVAL, APPROVED, QUEUED,
    # PARTIALLY_PUBLISHED, PUBLISHED, FAILED, CANCELLED
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True, nullable=False)

    # Current approval event pointer (append-only ledger tracks full history)
    current_approval_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    story = relationship("Story")
    story_version = relationship("StoryVersion")
    primary_media = relationship("MediaAsset", foreign_keys=[primary_media_asset_id])
    primary_derivative = relationship("MediaDerivative", foreign_keys=[primary_derivative_id])
    visual_asset = relationship("VisualAsset", foreign_keys=[visual_asset_id])
    subtitle_track = relationship("SubtitleTrack", foreign_keys=[subtitle_track_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    payloads = relationship(
        "PlatformPayload", back_populates="package", cascade="all, delete-orphan"
    )
    jobs = relationship("PublishingJob", back_populates="package", cascade="all, delete-orphan")
    published_items = relationship("PublishedItem", back_populates="package")
    approval_events = relationship("PublishingApprovalEvent", back_populates="package")


class PlatformPayload(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Platform-specific adaptations (captions, aspect ratios, tags) for a package."""

    __tablename__ = "platform_payloads"
    __table_args__ = (
        UniqueConstraint(
            "package_id", "destination_type", "account_id", name="uq_platform_payload_target"
        ),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    package_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("publishing_packages.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    destination_type: Mapped[str] = mapped_column(String(32), nullable=False)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("connected_accounts.id", ondelete="CASCADE"), nullable=False
    )

    adapted_title: Mapped[str] = mapped_column(String(255), nullable=False)
    adapted_description: Mapped[str] = mapped_column(Text, nullable=False)
    adapted_caption: Mapped[str] = mapped_column(Text, default="", nullable=False)
    target_aspect_ratio: Mapped[str] = mapped_column(String(16), default="16:9", nullable=False)

    selected_derivative_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("media_derivatives.id", ondelete="SET NULL"), nullable=True
    )
    selected_thumbnail_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("visual_assets.id", ondelete="SET NULL"), nullable=True
    )
    custom_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    validation_status: Mapped[str] = mapped_column(
        String(32), default="PENDING", nullable=False
    )  # PENDING, VALID, INVALID
    validation_errors: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    # Relationships
    package = relationship("PublishingPackage", back_populates="payloads")
    account = relationship("ConnectedAccount")
    derivative = relationship("MediaDerivative", foreign_keys=[selected_derivative_id])
    thumbnail = relationship("VisualAsset", foreign_keys=[selected_thumbnail_id])


class PublishingApprovalEvent(Base, UUIDPrimaryKeyMixin):
    """Immutable, append-only compliance ledger recording human
    approval/rejection/invalidation events.
    """

    __tablename__ = "publishing_approval_events"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    package_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("publishing_packages.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # APPROVED, REJECTED, INVALIDATED
    decided_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    publication_manifest_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    manifest_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # Mandatory for REJECTED/INVALIDATED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    package = relationship("PublishingPackage", back_populates="approval_events")
    decided_by = relationship("User", foreign_keys=[decided_by_user_id])


class PublishingJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Asynchronous job executing publication of a package to one specific connected account."""

    __tablename__ = "publishing_jobs"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    package_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("publishing_packages.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("connected_accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Stable publication identity: sha256(tenant_id + package_id + account_id + manifest_hash)
    publication_idempotency_key: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )

    # QUEUED, DISPATCHED, RUNNING, SUCCESS, FAILED, RATE_LIMITED, CANCELLED
    job_status: Mapped[str] = mapped_column(
        String(32), default="QUEUED", index=True, nullable=False
    )

    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    last_error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    safe_error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    package = relationship("PublishingPackage", back_populates="jobs")
    account = relationship("ConnectedAccount")
    attempt_records = relationship(
        "PublishingAttempt", back_populates="job", cascade="all, delete-orphan"
    )


class PublishingAttempt(Base, UUIDPrimaryKeyMixin):
    """Diagnostic log of each individual network/HTTP attempt executed for a job."""

    __tablename__ = "publishing_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_publishing_attempt_step"),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("publishing_jobs.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    http_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    platform_error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sanitized_error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # SUCCESS, TEMPORARY_FAILURE, PERMANENT_FAILURE, RATE_LIMITED, UNKNOWN
    outcome: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    job = relationship("PublishingJob", back_populates="attempt_records")


class PublishedItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Permanent public record of published external content."""

    __tablename__ = "published_items"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "external_item_id", name="uq_published_account_external_item"
        ),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    package_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("publishing_packages.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("connected_accounts.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    destination_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    external_item_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    external_url: Mapped[str] = mapped_column(String(500), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # PUBLIC, UNLISTED, PRIVATE
    visibility: Mapped[str] = mapped_column(String(32), default="PUBLIC", nullable=False)
    # ACTIVE, PROCESSING, DELETED, BLOCKED
    platform_state: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    package = relationship("PublishingPackage", back_populates="published_items")
    account = relationship("ConnectedAccount", back_populates="published_items")


class WebhookEvent(Base, UUIDPrimaryKeyMixin):
    """Idempotent audit record of platform webhooks and status callbacks."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "destination_type",
            "external_event_id",
            name="uq_webhook_events_destination_external_id",
        ),
    )

    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="SET NULL"), index=True, nullable=True
    )
    destination_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    signature_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # PROCESSED, DUPLICATE, FAILED, UNMATCHED
    processing_status: Mapped[str] = mapped_column(String(32), default="PROCESSED", nullable=False)
    sanitized_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
