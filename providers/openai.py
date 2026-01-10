"""OpenAI LLM provider implementation."""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI, APIConnectionError, APIError

from .base import BaseProvider, ProviderResponse
from .config import OpenAIConfig

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI LLM provider using official SDK."""

    def __init__(self, config: OpenAIConfig) -> None:
        """
        Initialize OpenAI provider.

        Args:
            config: OpenAIConfig instance with API credentials
        """
        super().__init__()
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            organization=config.organization_id,
        )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """
        Generate completion using OpenAI API.

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

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            logger.debug(f"OpenAI response received for model {self.config.model}")

            return ProviderResponse(
                content=response.choices[0].message.content,
                model=self.config.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                metadata={
                    "provider": "openai",
                    "finish_reason": response.choices[0].finish_reason,
                },
            )

        except APIConnectionError as e:
            logger.error(f"OpenAI connection error: {str(e)}")
            raise
        except APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise

    async def validate_connection(self) -> bool:
        """
        Validate OpenAI connection by checking API key.

        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Try to list models as a simple validation
            await self.client.models.list()
            logger.info("OpenAI connection validated")
            return True
        except Exception as e:
            logger.error(f"Failed to validate OpenAI connection: {str(e)}")
            return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "openai"
