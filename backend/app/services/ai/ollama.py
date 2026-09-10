"""Ollama local AI Provider implementation."""

from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.services.ai.base import AIProvider


class OllamaProvider(AIProvider):
    """Local inference provider targeting self-hosted Ollama."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.default_model = default_model or settings.OLLAMA_DEFAULT_MODEL
        self.timeout = timeout or settings.OLLAMA_REQUEST_TIMEOUT

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        format: Optional[str] = None,
    ) -> str:
        selected_model = model or self.default_model
        payload: Dict[str, Any] = {
            "model": selected_model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if options:
            payload["options"] = options
        if format:
            payload["format"] = format

        url = f"{self.base_url}/api/generate"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except httpx.HTTPError as e:
            logger.error(f"Ollama generation failed at {url}: {e}")
            raise RuntimeError(f"Ollama request error: {e}") from e

    async def generate_structured(
        self,
        prompt: str,
        schema_class: Any,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Generate structured response validated against a Pydantic schema."""
        raw_json = await self.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            options=options,
            format="json",
        )
        try:
            return schema_class.model_validate_json(raw_json)
        except Exception as e:
            logger.error(
                f"Failed to parse structured response: {e}. "
                f"Raw response: {raw_json[:150]}"
            )
            raise ValueError(f"Invalid structured JSON response from model: {e}") from e


    async def health_check(self) -> bool:
        """Check if local Ollama daemon is reachable."""
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            return False
