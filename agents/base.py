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
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from config import AgentConfig, ConfigParser
from providers import LLM, ProviderRegistry

NOTIFICATION = 12


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

        # Build create_agent parameters
        agent_params = {
            "model": self.llm,
            "tools": self.tools,
            "system_prompt": self.prompt,
            "name": self.name,
        }

        # Add optional structured output format
        if self.structured_output_type is not None:
            agent_params["response_format"] = self.structured_output_type

        # Merge with any additional kwargs passed to __init__
        agent_params.update(kwargs)

        self.logger.info(
            f"Creating agent with create_agent: {list(agent_params.keys())}"
        )

        # Create the agent graph using create_agent
        self.agent = create_agent(**agent_params)

        self.logger.info("Agent graph created successfully")

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

        # Invoke the agent with the input
        result = await self.agent.ainvoke(
            {"messages": [{"role": "user", "content": input_text}]},
            **invoke_kwargs,
        )

        self.logger.info(f"{self.name} execution completed")

        # Extract content from LangChain message format
        # create_agent returns a dict with "messages" key containing Message objects
        if isinstance(result, dict) and "messages" in result:
            messages = result["messages"]
            if messages:
                # Get the last message's content
                last_message = messages[-1]
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
        if isinstance(result, dict):
            return json.dumps(result)
        return str(result)
