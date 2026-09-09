"""Source model representing registered external and internal information sources."""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Source(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Registered feed/source for trend radar and content discovery."""

    __tablename__ = "sources"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(64), default="RSS", nullable=False
    )  # OFFICIAL, GOVERNMENT, WIRE, PUBLICATION, RSS, SOCIAL, USER_PROVIDED, OTHER

    feed_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    publisher_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    reliability_score: Mapped[Optional[float]] = mapped_column(Float, default=70.0, nullable=True)
    trust_level: Mapped[str] = mapped_column(
        String(32), default="MEDIUM", nullable=False
    )  # HIGH, MEDIUM, LOW, UNVERIFIED
    jurisdiction: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    polling_interval_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    # Rights metadata (e.g. rights_type, reuse_permitted, notes)
    rights_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Operational status
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    # Relationships
    tenant = relationship("Tenant")
    created_by = relationship("User")
    items = relationship("SourceItem", back_populates="source", cascade="all, delete-orphan")
