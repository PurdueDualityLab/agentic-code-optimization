"""Ollama LLM provider implementation."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .base import BaseProvider, ProviderResponse
from .config import OllamaConfig

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    """Ollama local LLM provider using HTTP API."""

    def __init__(self, config: OllamaConfig) -> None:
        """
        Initialize Ollama provider.

        Args:
            config: OllamaConfig instance with connection details
        """
        super().__init__()
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.timeout)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """
        Generate completion using Ollama API.

        Args:
            system_prompt: System message for the LLM
            user_prompt: User message for the LLM
            **kwargs: Additional parameters (temperature, max_tokens override)

        Returns:
            ProviderResponse with generated content
        """
        messages = self.format_messages(system_prompt, user_prompt)

        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "num_predict": max_tokens,
            "stream": False,
        }

        try:
            response = await self.client.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            logger.debug(f"Ollama response received for model {self.config.model}")

            return ProviderResponse(
                content=data.get("message", {}).get("content", ""),
                model=self.config.model,
                usage=data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0}),
                metadata={
                    "provider": "ollama",
                    "base_url": self.config.base_url,
                },
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API error: {e.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Ollama provider error: {str(e)}")
            raise

    async def validate_connection(self) -> bool:
        """
        Validate Ollama connection.

        Returns:
            True if Ollama is accessible, False otherwise
        """
        try:
            response = await self.client.get(f"{self.config.base_url}/api/tags")
            is_valid = response.status_code == 200
            if is_valid:
                logger.info(f"Ollama connection validated at {self.config.base_url}")
            else:
                logger.warning(f"Ollama returned status {response.status_code}")
            return is_valid
        except Exception as e:
            logger.error(f"Failed to validate Ollama connection: {str(e)}")
            return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "ollama"

    async def __aenter__(self) -> OllamaProvider:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.client.aclose()
