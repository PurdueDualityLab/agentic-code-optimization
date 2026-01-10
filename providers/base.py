"""Base provider interface for LLM integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderResponse:
    """Standard response format from any LLM provider."""

    content: str
    model: str
    usage: dict[str, int]
    metadata: dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


class BaseProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self) -> None:
        """Initialize the provider."""
        pass

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """
        Generate a completion from the LLM.

        Args:
            system_prompt: System message for the LLM
            user_prompt: User message for the LLM
            **kwargs: Additional provider-specific arguments

        Returns:
            ProviderResponse with content and metadata
        """
        pass

    @abstractmethod
    async def validate_connection(self) -> bool:
        """
        Validate that the provider is accessible.

        Returns:
            True if connection is valid, False otherwise
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of this provider.

        Returns:
            Provider identifier (e.g., "ollama", "openai", "anthropic")
        """
        pass

    def format_messages(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> list[dict[str, str]]:
        """
        Format messages into standard chat format.

        Args:
            system_prompt: System message
            user_prompt: User message

        Returns:
            List of message dicts with role and content
        """
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
