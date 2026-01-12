"""Simple BaseAgent for multi-agent code optimization using tools.

This module provides a declarative agent framework where:
- Child classes define prompt, tools, and return_state_field as class attributes
- __new__ validates required attributes
- __init__ initializes the LLM with bound tools
- run() executes the agentic loop with messages
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import BaseTool
from langsmith import traceable

from config import AgentConfig, ConfigParser
from providers import LLM, ProviderRegistry

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base agent class for code analysis with declarative tool binding.

    Subclasses must define:
        prompt (str): System prompt for the agent
        tools (list[BaseTool]): Available tools
        return_state_field (str): Name of field to return results in
    """

    # Class attributes to be overridden
    prompt: str
    tools: list[BaseTool]
    return_state_field: str

    # Optional configuration
    temperature: float
    max_iterations: int
    provider_name: str

    def __new__(cls):
        """Validate that required class attributes are defined."""
        if "prompt" not in cls.__dict__:
            raise ValueError(f"{cls.__name__} must define 'prompt' class attribute")
        if "tools" not in cls.__dict__:
            raise ValueError(f"{cls.__name__} must define 'tools' class attribute")
        if "return_state_field" not in cls.__dict__:
            raise ValueError(f"{cls.__name__} must define 'return_state_field' class attribute")

        instance = super().__new__(cls)
        instance.config = ConfigParser.get(AgentConfig)

        if "provider_name" not in cls.__dict__:
            instance.provider_name = instance.config.default_provider
        if "temperature" not in cls.__dict__:
            instance.temperature = instance.config.temperature
        if "max_iterations" not in cls.__dict__:
            instance.max_iterations = instance.config.max_iterations

        return instance

    def __init__(self):
        """Initialize agent with provider and tool binding."""
        self.name = self.__class__.__name__

        # Map tools by name for easy access
        self.tools_by_name = {tool.name: tool for tool in self.tools}

        # Initialize llm
        self.llm = ProviderRegistry.get(self.provider_name, LLM)
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # Message history for tracking conversation
        self.messages = []
        self.iteration_count = 0
        self.final_result = None

    @traceable(name="agent_run", tags=["agent"])
    async def run(self, input_text: str) -> str:
        """Execute the agent with the given input.

        Args:
            input_text: Input text for the agent to process

        Returns:
            Final result from the agent
        """
        self.messages = [{"role": "user", "content": input_text}]
        self.iteration_count = 0

        while self.iteration_count < self.max_iterations:
            # Call LLM with tools
            response = await self.llm_with_tools.generate(
                system_prompt=self.prompt,
                user_prompt=input_text,
                tools=self.tools,
                temperature=self.temperature,
            )

            self.messages.append({"role": "assistant", "content": response.content})
            logger.info(f"{self.name} iteration {self.iteration_count + 1}/{self.max_iterations}")

            # Check if response contains tool calls
            tool_calls = self._extract_tool_calls(response.content)

            if tool_calls:
                # Execute tools
                for tool_call in tool_calls:
                    tool_result = await self._execute_tool(tool_call)
                    self.messages.append({"role": "tool", "content": str(tool_result)})
                    logger.info(f"{self.name} executed tool: {tool_call.get('name', 'unknown')}")
            else:
                # No tool calls - this is the final response
                self.final_result = response.content
                return response.content

            self.iteration_count += 1

        logger.warning(f"{self.name} reached max iterations")
        self.final_result = "Max iterations reached"
        return self.final_result

    def _extract_tool_calls(self, response: str) -> list[dict[str, Any]]:
        """Extract tool calls from LLM response.

        Supports extraction from JSON tool_calls format.

        Args:
            response: LLM response text

        Returns:
            List of tool call dictionaries with 'name' and 'args' keys
        """
        tool_calls = []

        # Look for tool_calls JSON pattern in response
        # Pattern: "tool_calls": [{"name": "...", "args": {...}}]
        import re

        pattern = r'"tool_calls"\s*:\s*(\[.*?\])'
        match = re.search(pattern, response, re.DOTALL)

        if match:
            try:
                tool_calls_json = json.loads(match.group(1))
                if isinstance(tool_calls_json, list):
                    tool_calls = tool_calls_json
            except json.JSONDecodeError:
                pass

        return tool_calls

    async def _execute_tool(self, tool_call: dict[str, Any]) -> str:
        """Execute a single tool with given arguments.

        Args:
            tool_call: Dictionary with 'name' and 'args' keys

        Returns:
            Tool execution result as string
        """
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})

        if not tool_name:
            return "Error: No tool name provided"

        tool = self.tools_by_name.get(tool_name)
        if not tool:
            return f"Error: Tool '{tool_name}' not found"

        try:
            # Execute tool
            if callable(tool.func):
                result = tool.func(**tool_args) if tool_args else tool.func()
            else:
                result = tool.invoke(tool_args)

            return str(result)
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {str(e)}")
            return f"Error: {str(e)}"

    def get_langgraph_output(self) -> dict[str, Any]:
        """Get output in LangGraph compatible format.

        Returns:
            Dictionary with return_state_field as key
        """
        return {
            self.return_state_field: self.final_result or "",
            f"{self.return_state_field}_state": {
                "messages": self.messages,
                "iterations": self.iteration_count,
            },
        }
