"""Provider registry for managing and loading LLM providers."""

from __future__ import annotations

import logging
from typing import Type

from config.parser import ConfigParser

from config.providers import AnthropicConfig, OllamaConfig, OpenAIConfig

from .anthropic import AnthropicProvider
from .base import BaseProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry for dynamically managing LLM providers."""

    _providers: dict[str, Type[BaseProvider]] = {
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
    }

    _config_map: dict[str, Type] = {
        "ollama": OllamaConfig,
        "openai": OpenAIConfig,
        "anthropic": AnthropicConfig,
    }

    @classmethod
    def register(
        cls,
        name: str,
        provider_class: Type[BaseProvider],
        config_class: Type | None = None,
    ) -> None:
        """
        Register a new provider.

        Args:
            name: Unique provider identifier
            provider_class: Provider class (must inherit from BaseProvider)
            config_class: Config class (must inherit from SubSectionParser)
        """
        if not issubclass(provider_class, BaseProvider):
            raise TypeError(f"{provider_class} must inherit from BaseProvider")

        cls._providers[name] = provider_class
        if config_class:
            cls._config_map[name] = config_class

        logger.info(f"Registered provider: {name}")

    @classmethod
    def create(cls, provider_name: str) -> BaseProvider:
        """
        Create a provider instance from config.

        Args:
            provider_name: Name of the provider to instantiate

        Returns:
            Initialized provider instance

        Raises:
            ValueError: If provider name not found in registry
        """
        if provider_name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown provider: {provider_name}. Available: {available}"
            )

        provider_class = cls._providers[provider_name]
        config_class = cls._config_map.get(provider_name)

        if config_class is None:
            logger.warning(f"No config class for provider {provider_name}")
            return provider_class()

        try:
            config = ConfigParser.get(config_class)
            logger.info(f"Created {provider_name} provider with config")
            return provider_class(config)
        except Exception as e:
            logger.error(f"Failed to create {provider_name} provider: {str(e)}")
            raise

    @classmethod
    def get_available(cls) -> list[str]:
        """
        Get list of available providers.

        Returns:
            List of registered provider names
        """
        return list(cls._providers.keys())

    @classmethod
    def is_registered(cls, provider_name: str) -> bool:
        """
        Check if provider is registered.

        Args:
            provider_name: Name of provider to check

        Returns:
            True if provider is registered, False otherwise
        """
        return provider_name in cls._providers

    @classmethod
    async def validate_provider(cls, provider_name: str) -> bool:
        """
        Validate a provider's connection.

        Args:
            provider_name: Name of provider to validate

        Returns:
            True if provider connection is valid, False otherwise
        """
        try:
            provider = cls.create(provider_name)
            is_valid = await provider.validate_connection()
            logger.info(f"Provider {provider_name} validation: {is_valid}")
            return is_valid
        except Exception as e:
            logger.error(f"Provider {provider_name} validation failed: {str(e)}")
            return False
