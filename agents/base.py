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

from beautilog import logger
from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, MessagesState, StateGraph

from config import AgentConfig, ConfigParser
from providers import LLM, ProviderRegistry

NOTIFICATION = 12
TOOL_CALL = 14
LLM_CALL = 15


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
        self.iteration_count = 0  # Counts only LLM calls
        self.tools_used_count = 0  # Counts total tool executions
        self.tools_used_names = []  # Track which tools were used
        self.final_result = None
        self.logger = logger.getChild(self.name)

    def _llm_call(self, state: MessagesState) -> dict[str, Any]:
        """LLM node - decides whether to call a tool or respond."""
        self.iteration_count += 1
        self.logger.info(f" LLM Call #{self.iteration_count} - Invoking LLM")
        self.logger.log(LLM_CALL, f"State dict: {state}")
        self.logger.log(LLM_CALL, f"Messages count: {len(state['messages'])}")

        messages = [SystemMessage(content=self.prompt)] + state["messages"]
        self.logger.log(LLM_CALL, f"Total messages to LLM: {len(messages)}")
        response = self.llm_with_tools.invoke(messages)
        self.logger.log(LLM_CALL, f"LLM response type: {type(response).__name__}")

        # Check if this response contains tool calls
        has_tools = hasattr(response, "tool_calls") and response.tool_calls
        if has_tools:
            self.logger.info(
                f"LLM Call #{self.iteration_count} - "
                f"Generated {len(response.tool_calls)} tool call(s)"
            )
            self.logger.log(LLM_CALL, f"Tool calls: {response.tool_calls}")
        else:
            self.logger.info(f"LLM Call #{self.iteration_count} - No tool calls, returning response")
            self.logger.log(LLM_CALL, f"Response content: {response.content if hasattr(response, 'content') else str(response)}")

        return {"messages": [response]}

    def _tool_node(self, state: MessagesState) -> dict[str, Any]:
        """Tool node - executes tool calls from LLM response."""
        results = []
        self.logger.log(TOOL_CALL, f"Tool node state dict: {state}")
        self.logger.log(TOOL_CALL, f"Messages in state: {len(state['messages'])}")
        last_message = state["messages"][-1]
        self.logger.log(TOOL_CALL, f"Last message type: {type(last_message).__name__}")
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            self.logger.info(
                f"Executing {len(last_message.tool_calls)} tool(s)"
            )
            self.logger.log(TOOL_CALL, f"Tool calls details: {last_message.tool_calls}")

            for idx, tool_call in enumerate(last_message.tool_calls, 1):
                tool_name = tool_call["name"]
                tool = self.tools_by_name.get(tool_name)
                self.logger.log(TOOL_CALL, f"Tool call args: {tool_call.get('args', {})}")

                if tool:
                    try:
                        self.logger.info(
                            f"Tool {idx}/{len(last_message.tool_calls)}: "
                            f"Executing '{tool_name}'"
                        )
                        observation = tool.invoke(tool_call["args"])
                        self.logger.log(TOOL_CALL, f"Tool observation: {observation}")
                        results.append(
                            ToolMessage(
                                content=str(observation),
                                tool_call_id=tool_call["id"],
                            )
                        )
                        self.tools_used_count += 1
                        if tool_name not in self.tools_used_names:
                            self.tools_used_names.append(tool_name)
                        self.logger.log(TOOL_CALL,
                            f"Tool '{tool_name}' completed "
                            f"(Total tools used: {self.tools_used_count})"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Tool '{tool_name}' failed: {str(e)}"
                        )
                        results.append(
                            ToolMessage(
                                content=f"Error: {str(e)}",
                                tool_call_id=tool_call["id"],
                            )
                        )
                else:
                    self.logger.warning(f"Tool '{tool_name}' not found")
                    results.append(
                        ToolMessage(
                            content=f"Error: Tool '{tool_name}' not found",
                            tool_call_id=tool_call["id"],
                        )
                    )
        else:
            self.logger.info("No tool calls to execute")
            self.logger.log(TOOL_CALL, f"Last message content: {last_message}")

        self.logger.log(TOOL_CALL, f"Returning {len(results)} tool messages")
        return {"messages": results}

    def _should_continue(self, state: MessagesState) -> Literal["tool_node", END]:
        """Conditional edge - route based on whether LLM made tool calls."""
        last_message = state["messages"][-1]

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tool_node"

        return END

    def run(self, input_text: str) -> str:
        """Execute the agent with the given input using LangGraph.

        Args:
            input_text: Input text for the agent to process

        Returns:
            Final result from the agent
        """
        self.logger.info(f"Starting agent execution")
        self.logger.info(f"Input length: {len(input_text)} characters")
        self.logger.info(f"Available tools: {list(self.tools_by_name.keys())}")
        self.logger.log(NOTIFICATION, f"Input text: {input_text[:200]}...")

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

        self.logger.info("StateGraph compiled successfully")

        # Compile the graph
        compiled_graph = agent_builder.compile()

        # Execute the graph
        self.logger.info("Invoking compiled graph")
        initial_messages = [HumanMessage(content=input_text)]
        self.logger.log(NOTIFICATION, f"Initial messages: {initial_messages}")
        result = compiled_graph.invoke({"messages": initial_messages})

        # Extract final response
        self.logger.info("Graph execution completed")
        self.logger.log(NOTIFICATION, f"Result state dict: {result}")
        final_messages = result["messages"]
        self.logger.log(NOTIFICATION, f"Final messages count: {len(final_messages)}")
        final_message = final_messages[-1]
        self.logger.log(NOTIFICATION, f"Final message type: {type(final_message).__name__}")
        if hasattr(final_message, "content"):
            self.final_result = final_message.content
        else:
            self.final_result = str(final_message)

        self.logger.log(NOTIFICATION, f"Final result: {self.final_result[:200] if self.final_result else 'None'}...")

        # Update messages history for compatibility
        self.messages = final_messages

        self.logger.info(
            f"Agent execution finished: "
            f"LLM Iterations: {self.iteration_count}, "
            f"Tools Used: {self.tools_used_count} "
            f"({len(self.tools_used_names)} unique tools), "
            f"Result length: {len(self.final_result) if self.final_result else 0}"
        )

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
                "tools_used_count": self.tools_used_count,
                "tools_used_names": self.tools_used_names,
                "unique_tools_count": len(self.tools_used_names),
            },
        }
