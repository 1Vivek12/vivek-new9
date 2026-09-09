"""Tests for minimal AIProvider interface and Ollama adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai.ollama import OllamaProvider


@pytest.mark.asyncio
async def test_ollama_provider_health_check_offline():
    """Verifies that health check returns False when endpoint is unreachable."""
    provider = OllamaProvider(base_url="http://localhost:99999")
    status = await provider.health_check()
    assert status is False


@pytest.mark.asyncio
async def test_ollama_provider_generate_text_contract():
    """Verifies generate_text request packaging with mocked client."""
    provider = OllamaProvider(base_url="http://localhost:11434")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": "Gorakhpur topic summary generated."}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        result = await provider.generate_text(
            prompt="Summarize the latest Gorakhpur railway developments",
            system_prompt="You are a professional news editor.",
        )
        assert "Gorakhpur topic summary" in result
