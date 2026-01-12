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
from typing import Any, Literal

from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, MessagesState, StateGraph

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

    def _llm_call(self, state: MessagesState) -> dict[str, Any]:
        """LLM node - decides whether to call a tool or respond."""
        messages = [SystemMessage(content=self.prompt)] + state["messages"]
        response = self.llm_with_tools.invoke(messages)
        logger.info(f"{self.name} LLM call completed")
        return {"messages": [response]}

    def _tool_node(self, state: MessagesState) -> dict[str, Any]:
        """Tool node - executes tool calls from LLM response."""
        results = []
        last_message = state["messages"][-1]

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                tool = self.tools_by_name.get(tool_call["name"])
                if tool:
                    try:
                        observation = tool.invoke(tool_call["args"])
                        results.append(
                            ToolMessage(
                                content=str(observation),
                                tool_call_id=tool_call["id"],
                            )
                        )
                        logger.info(f"{self.name} executed tool: {tool_call['name']}")
                    except Exception as e:
                        logger.error(
                            f"{self.name} tool execution failed for {tool_call['name']}: {str(e)}"
                        )
                        results.append(
                            ToolMessage(
                                content=f"Error: {str(e)}",
                                tool_call_id=tool_call["id"],
                            )
                        )
                else:
                    logger.warning(f"{self.name} tool not found: {tool_call['name']}")
                    results.append(
                        ToolMessage(
                            content=f"Error: Tool '{tool_call['name']}' not found",
                            tool_call_id=tool_call["id"],
                        )
                    )

        return {"messages": results}

    def _should_continue(self, state: MessagesState) -> Literal["tool_node", END]:
        """Conditional edge - route based on whether LLM made tool calls."""
        last_message = state["messages"][-1]

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tool_node"

        return END

    async def run(self, input_text: str) -> str:
        """Execute the agent with the given input using LangGraph.

        Args:
            input_text: Input text for the agent to process

        Returns:
            Final result from the agent
        """
        # Build the StateGraph
        agent_builder = StateGraph(MessagesState)

        # Add nodes
        agent_builder.add_node("llm_call", self._llm_call)
        agent_builder.add_node("tool_node", self._tool_node)

        # Add edges
        agent_builder.add_edge(START, "llm_call")
        agent_builder.add_conditional_edges(
            "llm_call",
            self._should_continue,
            {"tool_node": "tool_node", END: END},
        )
        agent_builder.add_edge("tool_node", "llm_call")

        # Compile the graph
        compiled_graph = agent_builder.compile()

        # Execute the graph
        initial_messages = [HumanMessage(content=input_text)]
        result = compiled_graph.invoke({"messages": initial_messages})

        # Extract final response
        final_messages = result["messages"]
        final_message = final_messages[-1]

        if hasattr(final_message, "content"):
            self.final_result = final_message.content
        else:
            self.final_result = str(final_message)

        # Update messages history for compatibility
        self.messages = final_messages
        self.iteration_count = len([m for m in final_messages if hasattr(m, "content")])

        return self.final_result

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
