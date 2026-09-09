"""Tenant-scoped analytics abstraction."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class AnalyticsProvider(ABC):
    """Abstract interface for tenant-scoped metrics and performance telemetry."""

    @abstractmethod
    async def track_event(
        self, tenant_id: str, event_name: str, properties: Dict[str, Any]
    ) -> None:
        """Record an analytics event strictly partitioned by tenant."""
        pass

    @abstractmethod
    async def get_tenant_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Fetch high-level KPI summary for an authorized tenant."""
        pass
