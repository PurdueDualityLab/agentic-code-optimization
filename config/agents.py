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

        # Middleware configuration
        enable_summarization: Enable automatic conversation summarization
        summarization_trigger_tokens: Token count that triggers summarization
        summarization_keep_messages: Number of recent messages to keep after summarization
        summarization_model: Model to use for summarization (defaults to main model if empty)

        enable_todo_list: Enable task planning with to-do list middleware

        enable_llm_tool_selector: Enable LLM-based tool filtering
        tool_selector_max_tools: Maximum number of tools to select per iteration
        tool_selector_always_include: Comma-separated list of tools to always include
        tool_selector_model: Model to use for tool selection (defaults to main model if empty)

        enable_tool_retry: Enable automatic retry for failed tool calls
        tool_retry_max_retries: Maximum number of retry attempts
        tool_retry_backoff_factor: Exponential backoff multiplier
        tool_retry_initial_delay: Initial delay in seconds before first retry

        enable_context_editing: Enable automatic context cleanup
        context_edit_trigger_tokens: Token count that triggers context editing
        context_edit_keep_tool_uses: Number of recent tool uses to keep

        enable_shell_tool: Enable persistent shell session
        shell_workspace_root: Root directory for shell operations (defaults to current working directory)

        enable_file_search: Enable glob and regex file search
        file_search_root_path: Root directory for file search (defaults to current working directory)
        file_search_use_ripgrep: Use ripgrep for faster searches if available
    """

    SECTION: ClassVar[str] = "agents"

    max_iterations: int = 10
    temperature: float = 0.3
    default_provider: str = "ollama"
    timeout: int = 60
    verbose: bool = False
    max_tokens: Optional[int] = None
    recursion_limit: int = 50

    # Middleware configuration
    enable_summarization: bool = False
    summarization_trigger_tokens: int = 4000
    summarization_keep_messages: int = 20
    summarization_model: str = ""

    enable_todo_list: bool = False

    enable_llm_tool_selector: bool = False
    tool_selector_max_tools: int = 5
    tool_selector_always_include: str = ""
    tool_selector_model: str = ""

    enable_tool_retry: bool = False
    tool_retry_max_retries: int = 3
    tool_retry_backoff_factor: float = 2.0
    tool_retry_initial_delay: float = 1.0

    enable_context_editing: bool = False
    context_edit_trigger_tokens: int = 100000
    context_edit_keep_tool_uses: int = 3

    enable_shell_tool: bool = False
    shell_workspace_root: str = ""

    enable_file_search: bool = False
    file_search_root_path: str = ""
    file_search_use_ripgrep: bool = True
