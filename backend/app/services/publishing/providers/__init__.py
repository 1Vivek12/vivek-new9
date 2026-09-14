"""Publishing providers package."""

from app.services.publishing.providers.base import (
    ProviderCapabilities,
    ProviderNotConfiguredError,
    ProviderPublishResult,
    PublishingProvider,
)
from app.services.publishing.providers.facebook import FacebookProvider
from app.services.publishing.providers.instagram import InstagramProvider
from app.services.publishing.providers.mock import MockPublishingProvider
from app.services.publishing.providers.registry import ProviderRegistry, provider_registry
from app.services.publishing.providers.website import WebsitePublishingProvider
from app.services.publishing.providers.whatsapp import WhatsAppProvider
from app.services.publishing.providers.youtube import YouTubeProvider

__all__ = [
    "PublishingProvider",
    "ProviderCapabilities",
    "ProviderPublishResult",
    "ProviderNotConfiguredError",
    "YouTubeProvider",
    "FacebookProvider",
    "InstagramProvider",
    "WhatsAppProvider",
    "WebsitePublishingProvider",
    "MockPublishingProvider",
    "ProviderRegistry",
    "provider_registry",
]
