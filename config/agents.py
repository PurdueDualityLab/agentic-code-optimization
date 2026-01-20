"""Configuration classes for agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Optional

from config.base import SubSectionParser


@dataclass
class AgentConfig(SubSectionParser):
    """Configuration for base agent behavior.

    Attributes:
        max_iterations: Maximum number of agentic loop iterations
        temperature: LLM temperature for determinism vs creativity (0.0-1.0)
        default_provider: Default LLM provider to use (ollama, openai, anthropic, gemini)
        timeout: Timeout for LLM calls in seconds
        verbose: Enable verbose logging for agent execution
        max_tokens: Maximum context tokens before truncation (None = no limit)
        recursion_limit: LangGraph recursion limit for agent graphs
    """

    SECTION: ClassVar[str] = "agents"

    max_iterations: int = 10
    temperature: float = 0.3
    default_provider: str = "ollama"
    timeout: int = 60
    verbose: bool = False
    max_tokens: Optional[int] = None
    recursion_limit: int = 50
