"""Simplified BaseAgent using langchain's create_agent.

This module provides a declarative agent framework where:
- Child classes define prompt, tools, and return_state_field as class attributes
- __new__ validates required attributes
- __init__ creates the agent using langchain's create_agent
- run() invokes the agent with the given input
"""

from __future__ import annotations

import json
from typing import Any

from beautilog import logger
from langchain.agents import create_agent
from langchain_core.messages import (AIMessage, HumanMessage, ToolMessage,
                                     trim_messages)
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from config import AgentConfig, ConfigParser
from providers import LLM, ProviderRegistry

LLM_CALL = logger.LLM_CALL
TOOL_CALL = logger.TOOL_CALL
NOTIFICATION = logger.NOTIFICATION


class BaseAgent:
    """Base agent class for code analysis using langchain's create_agent.

    Subclasses must define:
        prompt (str): System prompt for the agent
        tools (list[BaseTool]): Available tools
        return_state_field (str): Name of field to return results in
    """

    # Class attributes to be overridden
    prompt: str
    tools: list[BaseTool]
    structured_output_type: BaseModel | None = None
    return_state_field: str

    # Optional configuration
    temperature: float = 0.7
    max_iterations: int = 20
    provider_name: str = ""
    config: AgentConfig         # Populated in __new__

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

        if not cls.provider_name or cls.provider_name == "":
            instance.provider_name = instance.config.default_provider
        if "temperature" not in cls.__dict__:
            instance.temperature = instance.config.temperature
        if "max_iterations" not in cls.__dict__:
            instance.max_iterations = instance.config.max_iterations

        return instance

    def __init__(self, **kwargs: Any):
        """Initialize agent using langchain's create_agent.

        Args:
            **kwargs: Additional arguments to pass to create_agent
        """
        self.name = self.__class__.__name__
        self.logger = logger.getChild(self.name)

        # Get LLM provider
        self.llm = ProviderRegistry.get(self.provider_name, LLM)
        model = self.llm
        if self.structured_output_type is not None and hasattr(self.llm, "with_structured_output"):
            wrapped = self.llm.with_structured_output(self.structured_output_type)
            if hasattr(wrapped, "bind_tools"):
                model = wrapped

        # Build create_agent parameters
        agent_params = {
            "model": model,
            "tools": self.tools,
            "system_prompt": self.prompt,
            "name": self.name,
        }

        # Add token truncation middleware if max_tokens configured
        if self.config.max_tokens:
            agent_params["messages_modifier"] = trim_messages(
                max_tokens=self.config.max_tokens,
                strategy="last",
                token_counter=self.llm,
            )

        # Merge with any additional kwargs passed to __init__
        agent_params.update(kwargs)

        self.logger.info(
            f"Creating agent with create_agent: {list(agent_params.keys())}"
        )

        # Create the agent graph using create_agent
        self.agent = create_agent(**agent_params)

        self.logger.info("Agent graph created successfully")

    def _log_llm_input(self, messages: list) -> None:
        """Log LLM input messages.

        Args:
            messages: List of messages being sent to the LLM
        """
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            content = getattr(msg, "content", str(msg))
            # Truncate long content
            if isinstance(content, str) and len(content) > 500:
                content = content[:500] + "... (truncated)"
            self.logger.log(LLM_CALL, f"Message {i + 1} ({msg_type}): {content}")

    def _log_llm_output(self, response: Any) -> None:
        """Log LLM output response.

        Args:
            response: Response from the LLM (typically an AIMessage object)
        """
        # Simply log the entire response object
        self.logger.log(LLM_CALL, f"LLM Response Object:\n{response}")

    def _log_tool_execution(self, tool_name: str, tool_input: dict, tool_output: Any) -> None:
        """Log tool execution details.

        Args:
            tool_name: Name of the tool being executed
            tool_input: Input arguments to the tool
            tool_output: Output from the tool
        """
        self.logger.log(TOOL_CALL, f"Input: {json.dumps(tool_input, indent=2)[:300]}")

        # Truncate long output
        output_str = str(tool_output)
        if len(output_str) > 500:
            output_str = output_str[:500] + "... (truncated)"
        self.logger.log(TOOL_CALL, f"Output: {output_str}")

    async def run(self, input_text: str, **invoke_kwargs: Any) -> str:
        """Execute the agent with the given input.

        Args:
            input_text: Input text for the agent to process
            **invoke_kwargs: Additional arguments to pass to agent.invoke()

        Returns:
            Final result from the agent as a JSON string
        """
        self.logger.info("Starting agent execution")
        self.logger.info(f"Input length: {len(input_text)} characters")
        self.logger.log(NOTIFICATION, f"Input text: {input_text[:200]}...")

        # Track iteration count
        iteration = 0

        # Stream events to log LLM calls and tool executions
        final_result = None
        input_messages = {"messages": [{"role": "user", "content": input_text}]}

        if "config" not in invoke_kwargs:
            invoke_kwargs["config"] = {"recursion_limit": self.config.recursion_limit}
        elif isinstance(invoke_kwargs["config"], dict):
            invoke_kwargs["config"].setdefault(
                "recursion_limit", self.config.recursion_limit
            )

        async for event in self.agent.astream_events(
            input_messages,
            version="v2",
            **invoke_kwargs
        ):
            kind = event.get("event")
            name = event.get("name", "")
            data = event.get("data", {})

            # Log LLM calls
            if kind == "on_chat_model_start":
                iteration += 1
                self.logger.info(f"Iteration {iteration}: LLM call started")
                if "input" in data and "messages" in data["input"]:
                    self._log_llm_input(data["input"]["messages"])

            elif kind == "on_chat_model_end":
                self.logger.info(f"Iteration {iteration}: LLM call completed")
                if "output" in data:
                    self._log_llm_output(data["output"])

            # Log tool executions
            elif kind == "on_tool_start":
                tool_name = name
                tool_input = data.get("input", {})
                self.logger.info(f"Tool execution started: {tool_name}")
                self.logger.log(TOOL_CALL, f"Tool input: {json.dumps(tool_input, indent=2)[:300]}")

            elif kind == "on_tool_end":
                tool_name = name
                tool_output = data.get("output", "")
                self.logger.info(f"Tool execution completed: {tool_name}")
                self._log_tool_execution(tool_name, {}, tool_output)

            # Capture final result
            elif kind == "on_chain_end" and name == self.name:
                final_result = data.get("output")

        self.logger.info(f"{self.name} execution completed after {iteration} iterations")

        # Extract content from LangChain message format
        if final_result and isinstance(final_result, dict) and "messages" in final_result:
            messages = final_result["messages"]
            if messages:
                # Get the last message's content
                last_message = messages[-1]
                
                # Prefer .text when available (avoids Gemini extras/signature)
                if hasattr(last_message, "text") and isinstance(last_message.text, str):
                    return last_message.text
                
                if hasattr(last_message, "content"):
                    content = last_message.content
                    # If content is already a string, return it
                    if isinstance(content, str):
                        return content
                    # If content is a dict (structured output), convert to JSON
                    elif isinstance(content, dict):
                        return json.dumps(content)
                    else:
                        return str(content)

        # Fallback: handle other return types
        if isinstance(final_result, dict):
            return json.dumps(final_result)
        return str(final_result) if final_result else ""
