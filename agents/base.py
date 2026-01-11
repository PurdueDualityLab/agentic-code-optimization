"""Base agent class for multi-agent code optimization using LangGraph.

This module provides a declarative agent framework that:
1. Uses __new__ to process class-level declarative attributes
2. Manages tool binding and execution
3. Implements the agentic loop (think -> tool use -> observe)
4. Integrates with the provider system for LLM interactions
5. Manages state for LangGraph workflow integration
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, Type

from langchain_core.tools import BaseTool

from config.agents import AgentConfig
from config.parser import ConfigParser
from config.providers import BaseProviderConfig
from providers.base import BaseProvider
from providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Status of agent execution."""

    IDLE = "idle"
    THINKING = "thinking"
    USING_TOOL = "using_tool"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class ToolResult:
    """Result from a single tool execution."""

    tool_name: str
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentState:
    """State managed by an agent during execution."""

    agent_name: str
    status: AgentStatus = AgentStatus.IDLE
    messages: list[dict[str, str]] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    final_result: Optional[str] = None
    iteration_count: int = 0
    max_iterations: int = 10
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for LangGraph integration."""
        return {
            "agent_name": self.agent_name,
            "status": self.status.value,
            "messages": self.messages,
            "tool_results": [
                {
                    "tool_name": tr.tool_name,
                    "success": tr.success,
                    "output": tr.output,
                    "error": tr.error,
                    "execution_time": tr.execution_time,
                    "metadata": tr.metadata,
                }
                for tr in self.tool_results
            ],
            "final_result": self.final_result,
            "iteration_count": self.iteration_count,
            "max_iterations": self.max_iterations,
            "created_at": self.created_at.isoformat(),
            "last_updated_at": self.last_updated_at.isoformat(),
            "metadata": self.metadata,
        }


class BaseAgent(ABC):
    """Abstract base class for declarative agents in the code optimization system.

    This class implements a declarative pattern where child classes define their
    behavior through class-level attributes. Agent configuration is loaded from
    config.ini [agents] section, allowing class attributes to override config values.

    Class-level attributes (all public, no underscore prefix):
        - prompt: str - System prompt for the agent (required)
        - tools: list[BaseTool] - Tools available to the agent (required)
        - return_state_field: str - Name of field to return in LangGraph state (required)
        - provider_name: str - Provider to use (overrides config: default_provider)
        - max_iterations: int - Maximum agentic loop iterations (overrides config)
        - temperature: float - LLM temperature (overrides config)

    Configuration Priority (highest to lowest):
        1. Explicit class attribute (if defined in subclass)
        2. Value from config.ini [agents] section

    The __new__ method:
        1. Loads agent configuration from config.ini
        2. Resolves configuration values with proper priority
        3. Validates required attributes
        4. Binds tools to the instance
        5. Initializes LLM provider
        6. Sets up agent state

    Example:
        class AnalysisAgent(BaseAgent):
            prompt = "You are a code analysis expert..."
            tools = [analyze_complexity_tool, detect_issues_tool]
            return_state_field = "analysis_results"
            temperature = 0.2  # Override config value
            # max_iterations will come from config.ini if not explicitly set
    """

    # Declarative class-level attributes (override in subclasses)
    # No underscore prefix - these are public configuration attributes
    prompt: str
    tools: list[BaseTool]
    return_state_field: str
    provider_name: str
    max_iterations: int
    temperature: float

    def __new__(cls, *args: Any, **kwargs: Any) -> BaseAgent:
        """Process declarative class attributes and validate agent configuration.

        This __new__ implementation:
        1. Loads agent configuration from config.ini
        2. Applies config values, allowing class attributes to override
        3. Validates that required attributes are defined
        4. Binds tools to the instance
        5. Initializes LLM provider
        6. Sets up agent state

        Raises:
            ValueError: If prompt is not defined or is empty
            ValueError: If return_state_field is not a valid identifier
            TypeError: If tools are not BaseTool instances
        """
        instance = super().__new__(cls)

        # Load agent configuration from config.ini
        agent_config = ConfigParser.get(AgentConfig)

        # Check which attributes are explicitly set (not inherited defaults)
        # vs which should come from config
        has_explicit_provider = "provider_name" in cls.__dict__
        has_explicit_max_iterations = "max_iterations" in cls.__dict__
        has_explicit_temperature = "temperature" in cls.__dict__

        # Resolve values with priority: explicit class attribute > config file
        provider_name = (
            cls.provider_name
            if has_explicit_provider
            else agent_config.default_provider
        )
        max_iterations = (
            cls.max_iterations
            if has_explicit_max_iterations
            else agent_config.max_iterations
        )
        temperature = (
            cls.temperature
            if has_explicit_temperature
            else agent_config.temperature
        )

        # Validate required attributes
        if not cls.prompt or not isinstance(cls.prompt, str):
            raise ValueError(
                f"{cls.__name__} must define a non-empty 'prompt' class attribute"
            )

        if not cls.return_state_field or not cls.return_state_field.replace("_", "").isalnum():
            raise ValueError(
                f"{cls.__name__} must define a valid 'return_state_field' "
                f"(got: {cls.return_state_field})"
            )

        # Validate and bind tools
        bound_tools = []
        for tool in cls.tools:
            if not isinstance(tool, BaseTool):
                raise TypeError(
                    f"{cls.__name__}.tools must contain BaseTool instances, "
                    f"got {type(tool).__name__}"
                )
            bound_tools.append(tool)

        # Store processed attributes on the instance (public, no underscore prefix)
        instance.prompt = cls.prompt
        instance.tools = bound_tools
        instance.return_state_field = cls.return_state_field
        instance.provider_name = provider_name
        instance.max_iterations = max_iterations
        instance.temperature = temperature

        # Internal state attributes (with underscore prefix)
        instance._agent_name = cls.__name__
        instance._agent_config = agent_config
        instance._state = AgentState(
            agent_name=instance._agent_name,
            max_iterations=instance.max_iterations,
        )

        # Initialize provider (lazy-loaded)
        instance._provider: Optional[BaseProvider] = None
        instance._provider_config: Optional[BaseProviderConfig] = None

        logger.info(
            f"Initialized agent {instance._agent_name} with "
            f"{len(bound_tools)} tools, max_iterations={instance.max_iterations}, "
            f"temperature={instance.temperature}, provider={instance.provider_name}"
        )

        return instance

    @property
    def agent_config(self) -> AgentConfig:
        """Get the agent configuration loaded from config.ini.

        Returns:
            AgentConfig: The agent configuration instance
        """
        return self._agent_config

    @property
    def provider(self) -> BaseProvider:
        """Get or initialize the LLM provider lazily.

        Returns:
            BaseProvider: The configured LLM provider instance

        Raises:
            ValueError: If provider cannot be created
        """
        if self._provider is None:
            try:
                self._provider = ProviderRegistry.create(self.provider_name)
                logger.info(f"Initialized {self.provider_name} provider for {self._agent_name}")
            except Exception as e:
                logger.error(f"Failed to initialize provider: {str(e)}")
                raise ValueError(f"Cannot initialize provider {self.provider_name}") from e

        return self._provider

    @property
    def tool_names(self) -> list[str]:
        """Get the names of available tools."""
        return [tool.name for tool in self.tools]

    @property
    def state(self) -> AgentState:
        """Get the current agent state."""
        return self._state

    def _build_system_prompt(self) -> str:
        """Build the complete system prompt including tool information.

        Returns:
            str: System prompt with tool descriptions
        """
        system_prompt = self.prompt

        if self.tools:
            tool_descriptions = self._build_tool_descriptions()
            system_prompt += "\n\n" + tool_descriptions

        return system_prompt

    def _build_tool_descriptions(self) -> str:
        """Build descriptions of available tools for the LLM.

        Returns:
            str: Formatted tool descriptions
        """
        if not self.tools:
            return ""

        descriptions = ["Available Tools:", ""]
        for i, tool in enumerate(self.tools, 1):
            descriptions.append(f"{i}. {tool.name}")
            if tool.description:
                descriptions.append(f"   Description: {tool.description}")
            descriptions.append("")

        return "\n".join(descriptions)

    async def _call_llm(self, user_message: str) -> str:
        """Call the LLM with the given user message.

        Args:
            user_message: The user's input message

        Returns:
            str: The LLM's response

        Raises:
            Exception: If LLM call fails
        """
        system_prompt = self._build_system_prompt()

        try:
            response = await self.provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_message,
                temperature=self.temperature,
            )
            logger.debug(f"{self._agent_name} received response from LLM")
            return response.content
        except Exception as e:
            logger.error(f"LLM call failed: {str(e)}")
            raise

    async def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
        """Execute a single tool and return the result.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            ToolResult: Result of the tool execution

        Raises:
            ValueError: If tool is not found
        """
        start_time = datetime.utcnow()

        # Find the tool
        tool = None
        for t in self.tools:
            if t.name == tool_name:
                tool = t
                break

        if tool is None:
            error_msg = f"Tool '{tool_name}' not found in {self._agent_name}"
            logger.error(error_msg)
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=error_msg,
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
            )

        try:
            logger.info(f"{self._agent_name} executing tool: {tool_name}")

            # Check if tool is async or sync
            if inspect.iscoroutinefunction(tool.func):
                output = await tool.func(**tool_input)
            else:
                output = tool.func(**tool_input)

            execution_time = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"{self._agent_name} tool execution completed: {tool_name} ({execution_time:.2f}s)")

            return ToolResult(
                tool_name=tool_name,
                success=True,
                output=str(output),
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Tool execution failed: {str(e)}"
            logger.error(f"{self._agent_name} - {error_msg}")

            return ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=error_msg,
                execution_time=execution_time,
            )

    def _parse_tool_calls(self, response: str) -> list[tuple[str, dict[str, Any]]]:
        """Parse tool calls from LLM response.

        The LLM should respond in a specific format to indicate tool calls.
        This implementation looks for JSON blocks containing tool_name and tool_input.

        Format expected:
        {
            "action": "tool_name",
            "action_input": {"param1": "value1", "param2": "value2"}
        }

        Args:
            response: The LLM response to parse

        Returns:
            list[tuple[str, dict]]: List of (tool_name, tool_input) tuples

        Raises:
            ValueError: If response cannot be parsed
        """
        tool_calls = []

        # Try to extract JSON blocks from the response
        import re

        json_pattern = r'\{[^{}]*"action"[^{}]*"action_input"[^{}]*\}'
        matches = re.findall(json_pattern, response, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match)
                tool_name = data.get("action", "").strip()
                tool_input = data.get("action_input", {})

                if tool_name and tool_name in self.tool_names:
                    tool_calls.append((tool_name, tool_input))
                else:
                    logger.warning(f"Unknown tool in response: {tool_name}")

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from response: {str(e)}")
                continue

        return tool_calls

    def _format_tool_results(self, tool_results: list[ToolResult]) -> str:
        """Format tool results for inclusion in the next LLM message.

        Args:
            tool_results: List of tool execution results

        Returns:
            str: Formatted results for LLM
        """
        if not tool_results:
            return ""

        formatted = ["Tool Results:", ""]

        for result in tool_results:
            formatted.append(f"Tool: {result.tool_name}")
            if result.success:
                formatted.append(f"Status: Success")
                formatted.append(f"Output: {result.output[:500]}")  # Truncate long outputs
            else:
                formatted.append(f"Status: Failed")
                formatted.append(f"Error: {result.error}")
            formatted.append("")

        return "\n".join(formatted)

    async def _agentic_loop(
        self,
        initial_input: str,
        should_continue: Optional[Callable[[list[ToolResult]], bool]] = None,
    ) -> str:
        """Execute the main agentic loop: think -> tool use -> observe.

        This loop continues until:
        1. The LLM decides to stop (doesn't call a tool)
        2. Maximum iterations reached
        3. Custom should_continue callback returns False
        4. An error occurs

        Args:
            initial_input: The initial input to the agent
            should_continue: Optional callback to determine if loop should continue.
                            Receives list of most recent tool results.

        Returns:
            str: The final result from the agent

        Raises:
            RuntimeError: If max iterations exceeded
        """
        logger.info(f"{self._agent_name} starting agentic loop with input: {initial_input[:100]}...")

        self._state.status = AgentStatus.THINKING
        current_input = initial_input
        accumulated_results: list[ToolResult] = []

        while self._state.iteration_count < self._state.max_iterations:
            self._state.iteration_count += 1
            logger.info(
                f"{self._agent_name} iteration {self._state.iteration_count}/{self._state.max_iterations}"
            )

            try:
                # Step 1: Think - Call LLM
                self._state.status = AgentStatus.THINKING
                llm_response = await self._call_llm(current_input)
                self._state.messages.append({"role": "assistant", "content": llm_response})

                # Step 2: Check if LLM wants to use tools
                tool_calls = self._parse_tool_calls(llm_response)

                if not tool_calls:
                    # LLM didn't call any tools, so we're done
                    logger.info(f"{self._agent_name} completed - no tool calls in final response")
                    self._state.final_result = llm_response
                    self._state.status = AgentStatus.COMPLETE
                    return llm_response

                # Step 3: Use Tools - Execute all tool calls
                self._state.status = AgentStatus.USING_TOOL
                iteration_results: list[ToolResult] = []

                for tool_name, tool_input in tool_calls:
                    result = await self._execute_tool(tool_name, tool_input)
                    iteration_results.append(result)
                    self._state.tool_results.append(result)

                accumulated_results = iteration_results

                # Step 4: Observe - Prepare next input with tool results
                tool_results_text = self._format_tool_results(iteration_results)
                current_input = (
                    f"Previous response:\n{llm_response}\n\n{tool_results_text}\n\n"
                    "Please review the tool results and either use more tools or provide "
                    "a final response if the task is complete."
                )

                # Check if should continue
                if should_continue and not should_continue(iteration_results):
                    logger.info(f"{self._agent_name} stopped by should_continue callback")
                    self._state.final_result = llm_response
                    self._state.status = AgentStatus.COMPLETE
                    return llm_response

            except Exception as e:
                logger.error(f"{self._agent_name} error in agentic loop: {str(e)}")
                self._state.status = AgentStatus.ERROR
                self._state.metadata["error"] = str(e)
                raise RuntimeError(f"Agent loop failed: {str(e)}") from e

        # Max iterations exceeded
        logger.warning(
            f"{self._agent_name} reached maximum iterations ({self._state.max_iterations})"
        )
        self._state.status = AgentStatus.COMPLETE
        self._state.final_result = current_input
        return current_input

    async def run(self, input_text: str) -> str:
        """Run the agent with the given input.

        This is the main entry point for agent execution.

        Args:
            input_text: The input to process

        Returns:
            str: The final result from the agentic loop
        """
        try:
            logger.info(f"Starting {self._agent_name} execution")
            result = await self._agentic_loop(input_text)
            logger.info(f"{self._agent_name} execution completed successfully")
            return result
        except Exception as e:
            logger.error(f"{self._agent_name} execution failed: {str(e)}")
            raise

    def get_langgraph_output(self) -> dict[str, Any]:
        """Get agent output formatted for LangGraph workflow state.

        This returns a dictionary with the return_state_field as key
        and the final result as value, suitable for updating workflow state.

        Returns:
            dict[str, Any]: Output formatted for LangGraph state update
        """
        return {
            self.return_state_field: self._state.final_result,
            f"{self.return_state_field}_state": self._state.to_dict(),
        }

    def get_state_dict(self) -> dict[str, Any]:
        """Get the complete agent state as a dictionary.

        Returns:
            dict[str, Any]: Current agent state
        """
        return self._state.to_dict()

    def reset(self) -> None:
        """Reset the agent state for a new execution.

        This clears all execution history while keeping the agent configuration.
        """
        self._state = AgentState(
            agent_name=self._agent_name,
            max_iterations=self._state.max_iterations,
        )
        logger.info(f"{self._agent_name} state reset")
