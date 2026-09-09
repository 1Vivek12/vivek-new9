"""Story model representing editorial content items."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Story(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Core editorial Story entity scoped strictly to a tenant."""

    __tablename__ = "stories"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_story_tenant_slug"),)

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    category_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    assignment_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True
    )

    priority: Mapped[str] = mapped_column(
        String(32), default="NORMAL", nullable=False
    )  # LOW, NORMAL, HIGH, URGENT
    status: Mapped[str] = mapped_column(
        String(32), default="IDEA", index=True, nullable=False
    )

    editorial_owner_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Human Approval Gate tracking
    approved_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    category = relationship("Category", back_populates="stories")
    assignment = relationship("Assignment", back_populates="stories")
    editorial_owner = relationship("User", foreign_keys=[editorial_owner_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    approved_by = relationship("User", foreign_keys=[approved_by_user_id])
    sources = relationship("StorySource", back_populates="story", cascade="all, delete-orphan")
    versions = relationship(
        "StoryVersion",
        back_populates="story",
        cascade="all, delete-orphan",
        order_by="desc(StoryVersion.version_number)",
    )
