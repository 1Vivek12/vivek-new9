"""Tenant model representing an isolated workspace/organization."""

from typing import Any, Dict

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tenant workspace entity."""

    __tablename__ = "tenants"

    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    brand_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    memberships = relationship(
        "TenantMembership", back_populates="tenant", cascade="all, delete-orphan"
    )
    audit_logs = relationship(
        "AuditLog", back_populates="tenant", cascade="all, delete-orphan"
    )
