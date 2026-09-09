"""Tenant membership associating users with tenants and assigning scoped roles."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TenantMembership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Associates a User with a Tenant under a specific RBAC role."""

    __tablename__ = "tenant_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_membership_tenant_user"),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(32), default="VIEWER", nullable=False
    )  # TENANT_OWNER, TENANT_ADMIN, EDITOR, REPORTER, CREATOR, VIEWER

    # Relationships
    tenant = relationship("Tenant", back_populates="memberships")
    user = relationship("User", back_populates="memberships")
