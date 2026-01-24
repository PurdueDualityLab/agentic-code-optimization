"""Simplified BaseAgent using langchain's create_agent.

This module provides a declarative agent framework where:
- Child classes define prompt, tools, and return_state_field as class attributes
- __new__ validates required attributes
- __init__ creates the agent using langchain's create_agent
- run() invokes the agent with the given input
"""

from __future__ import annotations

import json
import os
from typing import Any

from beautilog import logger
from langchain.agents import create_agent
from langchain.agents.middleware import (ClearToolUsesEdit,
                                         ContextEditingMiddleware,
                                         FilesystemFileSearchMiddleware,
                                         HostExecutionPolicy,
                                         LLMToolSelectorMiddleware,
                                         ShellToolMiddleware,
                                         SummarizationMiddleware,
                                         TodoListMiddleware,
                                         ToolRetryMiddleware)
from langchain_core.messages import trim_messages
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

    def _build_middleware(self) -> list:
        """Build middleware list based on configuration.

        Returns:
            List of middleware instances to pass to create_agent
        """
        middleware = []

        # 1. Summarization Middleware
        if self.config.enable_summarization:
            summarization_model = self.config.summarization_model or self.provider_name
            self.logger.info(
                f"Enabling SummarizationMiddleware (trigger={self.config.summarization_trigger_tokens} tokens, "
                f"keep={self.config.summarization_keep_messages} messages, model={summarization_model})"
            )
            middleware.append(
                SummarizationMiddleware(
                    model=summarization_model,
                    trigger=("tokens", self.config.summarization_trigger_tokens),
                    keep=("messages", self.config.summarization_keep_messages),
                )
            )

        # 2. To-do List Middleware
        if self.config.enable_todo_list:
            self.logger.info("Enabling TodoListMiddleware for task planning")
            middleware.append(TodoListMiddleware())

        # 3. LLM Tool Selector Middleware
        if self.config.enable_llm_tool_selector:
            tool_selector_model = self.config.tool_selector_model or self.provider_name
            always_include = []
            if self.config.tool_selector_always_include:
                always_include = [
                    tool.strip()
                    for tool in self.config.tool_selector_always_include.split(",")
                ]
            self.logger.info(
                f"Enabling LLMToolSelectorMiddleware (max_tools={self.config.tool_selector_max_tools}, "
                f"model={tool_selector_model}, always_include={always_include})"
            )
            middleware.append(
                LLMToolSelectorMiddleware(
                    model=tool_selector_model,
                    max_tools=self.config.tool_selector_max_tools,
                    always_include=always_include,
                )
            )

        # 4. Tool Retry Middleware
        if self.config.enable_tool_retry:
            self.logger.info(
                f"Enabling ToolRetryMiddleware (max_retries={self.config.tool_retry_max_retries}, "
                f"backoff={self.config.tool_retry_backoff_factor}, "
                f"initial_delay={self.config.tool_retry_initial_delay}s)"
            )
            middleware.append(
                ToolRetryMiddleware(
                    max_retries=self.config.tool_retry_max_retries,
                    backoff_factor=self.config.tool_retry_backoff_factor,
                    initial_delay=self.config.tool_retry_initial_delay,
                )
            )

        # 5. Context Editing Middleware
        if self.config.enable_context_editing:
            self.logger.info(
                f"Enabling ContextEditingMiddleware (trigger={self.config.context_edit_trigger_tokens} tokens, "
                f"keep={self.config.context_edit_keep_tool_uses} tool uses)"
            )
            middleware.append(
                ContextEditingMiddleware(
                    edits=[
                        ClearToolUsesEdit(
                            trigger=self.config.context_edit_trigger_tokens,
                            keep=self.config.context_edit_keep_tool_uses,
                        ),
                    ],
                )
            )

        # 6. Shell Tool Middleware
        if self.config.enable_shell_tool:
            workspace_root = self.config.shell_workspace_root or os.getcwd()
            self.logger.info(
                f"Enabling ShellToolMiddleware (workspace_root={workspace_root})"
            )
            middleware.append(
                ShellToolMiddleware(
                    workspace_root=workspace_root,
                    execution_policy=HostExecutionPolicy(),
                )
            )

        # 7. File Search Middleware
        if self.config.enable_file_search:
            search_root = self.config.file_search_root_path or os.getcwd()
            self.logger.info(
                f"Enabling FilesystemFileSearchMiddleware (root={search_root}, "
                f"ripgrep={self.config.file_search_use_ripgrep})"
            )
            middleware.append(
                FilesystemFileSearchMiddleware(
                    root_path=os.path.expanduser(search_root),
                    use_ripgrep=self.config.file_search_use_ripgrep,
                )
            )

        return middleware

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

        # Build middleware list based on configuration
        middleware = self._build_middleware()

        # Build create_agent parameters
        agent_params = {
            "model": model,
            "tools": self.tools,
            "system_prompt": self.prompt,
            "name": self.name,
        }

        # Add middleware if any are enabled
        if middleware:
            agent_params["middleware"] = middleware
            self.logger.info(f"Enabled {len(middleware)} middleware components")

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
        # Safely serialize tool input (may contain non-JSON-serializable middleware tools)
        try:
            tool_input_str = json.dumps(tool_input, indent=2)[:300]
        except (TypeError, ValueError):
            tool_input_str = str(tool_input)[:300]
        self.logger.log(TOOL_CALL, f"Input: {tool_input_str}")

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
                # Safely serialize tool input (may contain non-JSON-serializable middleware tools)
                try:
                    tool_input_str = json.dumps(tool_input, indent=2)[:300]
                except (TypeError, ValueError):
                    tool_input_str = str(tool_input)[:300]
                self.logger.log(TOOL_CALL, f"Tool input: {tool_input_str}")

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
