"""Provider registry for destination adapters."""

from __future__ import annotations

from typing import Dict

from app.db.models.publishing import DestinationType
from app.services.publishing.providers.base import PublishingProvider
from app.services.publishing.providers.facebook import FacebookProvider
from app.services.publishing.providers.instagram import InstagramProvider
from app.services.publishing.providers.mock import MockPublishingProvider
from app.services.publishing.providers.website import WebsitePublishingProvider
from app.services.publishing.providers.whatsapp import WhatsAppProvider
from app.services.publishing.providers.youtube import YouTubeProvider


class ProviderRegistry:
    """Registry maintaining active provider implementations for each destination type."""

    def __init__(self, use_mock: bool = False):
        self._providers: Dict[DestinationType, PublishingProvider] = {}
        self.use_mock = use_mock
        self._initialize_default_providers()

    def _initialize_default_providers(self):
        if self.use_mock:
            for dtype in DestinationType:
                self._providers[dtype] = MockPublishingProvider(destination_type=dtype)
        else:
            self._providers[DestinationType.YOUTUBE] = YouTubeProvider()
            self._providers[DestinationType.FACEBOOK] = FacebookProvider()
            self._providers[DestinationType.INSTAGRAM] = InstagramProvider()
            self._providers[DestinationType.WHATSAPP] = WhatsAppProvider()
            self._providers[DestinationType.WEBSITE] = WebsitePublishingProvider()

    def get_provider(self, destination_type: DestinationType | str) -> PublishingProvider:
        if isinstance(destination_type, str):
            destination_type = DestinationType(destination_type.upper())
        if destination_type not in self._providers:
            raise KeyError(f"No publishing provider registered for '{destination_type}'.")
        return self._providers[destination_type]

    def register_provider(
        self, destination_type: DestinationType, provider: PublishingProvider
    ) -> None:
        self._providers[destination_type] = provider

    def set_use_mock(self, use_mock: bool) -> None:
        self.use_mock = use_mock
        self._initialize_default_providers()


# Global default registry instance
provider_registry = ProviderRegistry()
