from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AIProvider(ABC):
    """Abstract interface for LLM / AI generation.

    Strictly limited to required capabilities:
    - generate_text (with format support, e.g. 'json')
    - generate_structured (schema-validated JSON output)
    - health_check
    """

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        format: Optional[str] = None,
    ) -> str:
        """Generate text from local or self-hosted AI model."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema_class: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> T:
        """Generate validated Pydantic model response from structured JSON output."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify model endpoint responsiveness."""
        pass
