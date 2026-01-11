"""Anthropic Claude LLM provider implementation."""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic, APIConnectionError, APIError

from config.providers import AnthropicConfig
from .base import BaseProvider, ProviderResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic Claude LLM provider using official SDK."""

    def __init__(self, config: AnthropicConfig) -> None:
        """
        Initialize Anthropic provider.

        Args:
            config: AnthropicConfig instance with API credentials
        """
        super().__init__()
        self.config = config
        self.client = Anthropic(api_key=config.api_key)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """
        Generate completion using Anthropic API.

        Args:
            system_prompt: System message for Claude
            user_prompt: User message for Claude
            **kwargs: Additional parameters (temperature, max_tokens override)

        Returns:
            ProviderResponse with generated content
        """
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        try:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt},
                ],
            )

            logger.debug(f"Anthropic response received for model {self.config.model}")

            return ProviderResponse(
                content=response.content[0].text,
                model=self.config.model,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                metadata={
                    "provider": "anthropic",
                    "stop_reason": response.stop_reason,
                },
            )

        except APIConnectionError as e:
            logger.error(f"Anthropic connection error: {str(e)}")
            raise
        except APIError as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise

    async def validate_connection(self) -> bool:
        """
        Validate Anthropic connection.

        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Try a simple API call with minimal tokens
            self.client.messages.create(
                model=self.config.model,
                max_tokens=1,
                messages=[
                    {"role": "user", "content": "Hi"},
                ],
            )
            logger.info("Anthropic connection validated")
            return True
        except Exception as e:
            logger.error(f"Failed to validate Anthropic connection: {str(e)}")
            return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "anthropic"
