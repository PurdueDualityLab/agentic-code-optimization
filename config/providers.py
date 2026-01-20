"""Configuration classes for LLM providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from config.base import SubSectionParser


@dataclass
class BaseProviderConfig(SubSectionParser):
    """Base configuration for all LLM providers."""

    SECTION: ClassVar[str] = "provider"

    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60


@dataclass
class OllamaConfig(SubSectionParser):
    """Configuration for Ollama provider."""

    SECTION: ClassVar[str] = "ollama"

    base_url: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    keep_alive: str = "5m"


@dataclass
class OpenAIConfig(SubSectionParser):
    """Configuration for OpenAI provider."""

    SECTION: ClassVar[str] = "openai"

    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    organization_id: str | None = None


@dataclass
class AnthropicConfig(SubSectionParser):
    """Configuration for Anthropic provider."""

    SECTION: ClassVar[str] = "anthropic"

    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60


@dataclass
class GeminiConfig(SubSectionParser):
    """Configuration for Gemini provider."""

    SECTION: ClassVar[str] = "gemini"

    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
