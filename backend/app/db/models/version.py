"""StoryVersion model representing immutable draft versions of editorial content."""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utc_now


class StoryVersion(Base, UUIDPrimaryKeyMixin):
    """Immutable snapshot of a Story's content and editorial state."""

    __tablename__ = "story_versions"
    __table_args__ = (
        UniqueConstraint("story_id", "version_number", name="uq_story_version_number"),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    story_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("stories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    headline: Mapped[str] = mapped_column(String(255), nullable=False)
    body_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )  # structured blocks or {"text": "..."}
    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_summary: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    tenant = relationship("Tenant")
    story = relationship("Story", back_populates="versions")
    created_by = relationship("User")
