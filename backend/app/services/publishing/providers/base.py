"""Publishing provider interface, capabilities, and result models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.publishing import ConnectedAccount, DestinationType, PlatformPayload
from app.services.publishing.vault import CredentialVault


class ProviderNotConfiguredError(Exception):
    """Raised when a real provider is called without required API keys or configuration."""

    pass


class ProviderPublishResult(BaseModel):
    """Normalized result returned by any publishing provider dispatch."""

    success: bool
    external_id: Optional[str] = None
    url: Optional[str] = None
    raw_response: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    is_mock: bool = False


class ProviderCapabilities(BaseModel):
    """Declares supported constraints and capabilities for a publishing destination."""

    destination_type: str
    max_video_duration_seconds: Optional[float] = None
    supports_resumable_upload: bool = False
    supported_aspect_ratios: List[str] = Field(default_factory=list)
    supported_media_types: List[str] = Field(default_factory=list)
    max_title_length: int = 100
    max_body_length: int = 5000
    supports_scheduling: bool = True


class PublishingProvider(ABC):
    """Abstract Base Class for all external and internal publishing destination providers."""

    destination_type: DestinationType
    is_mock: bool = False

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Returns the platform-specific capability specifications."""
        pass

    @abstractmethod
    async def publish(
        self,
        *,
        db: AsyncSession,
        payload: PlatformPayload,
        account: ConnectedAccount,
        vault: CredentialVault,
        media_assets: List[Dict[str, Any]],
    ) -> ProviderPublishResult:
        """Dispatches the publication payload to the target destination platform."""
        pass

    @abstractmethod
    async def ensure_valid_credentials(
        self,
        *,
        db: AsyncSession,
        account: ConnectedAccount,
        vault: CredentialVault,
    ) -> Dict[str, Any]:
        """Decrypts and validates (or refreshes) credentials for the connected account."""
        pass

    @abstractmethod
    async def check_health(
        self,
        *,
        account: ConnectedAccount,
        vault: CredentialVault,
    ) -> bool:
        """Probes the platform API to verify account health and active authorization."""
        pass
