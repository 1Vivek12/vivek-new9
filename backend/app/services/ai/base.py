"""Minimal AI Provider interface for Phase 1."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class AIProvider(ABC):
    """Abstract interface for LLM / AI generation.

    Strictly limited to Phase 1 required capabilities:
    - generate_text
    - health_check
    Embeddings and vector capabilities are deferred to future memory phases.
    """

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate text from local or self-hosted AI model."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify model endpoint responsiveness."""
        pass
