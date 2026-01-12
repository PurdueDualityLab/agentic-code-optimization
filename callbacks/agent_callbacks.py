"""Callbacks for agent execution events and state tracking."""

from __future__ import annotations

from typing import Any, Optional

from agents.base import AgentState, ToolResult
from agentic_logging import get_logger, ObservabilityManager, Trace

logger = get_logger(__name__)


class AgentExecutionCallback:
    """Callback handler for agent execution events."""

    def __init__(self, observability_manager: ObservabilityManager):
        """Initialize callback handler.

        Args:
            observability_manager: ObservabilityManager instance for tracing
        """
        self.observability_manager = observability_manager
        self.active_trace: Optional[Trace] = None

    def on_agent_start(self, agent_name: str, repo_path: str = "") -> None:
        """Called when agent starts.

        Args:
            agent_name: Name of the agent
            repo_path: Path being analyzed
        """
        self.active_trace = self.observability_manager.start_trace(agent_name, repo_path)
        logger.info(
            f"Agent {agent_name} started",
            extra={
                "trace_id": self.observability_manager.trace_id,
                "agent_name": agent_name,
                "status": "started",
            },
        )

    def on_iteration_start(self, iteration: int, max_iterations: int) -> None:
        """Called when an agent iteration starts.

        Args:
            iteration: Current iteration number
            max_iterations: Maximum iterations
        """
        if not self.active_trace:
            return

        metric = self.active_trace.add_metric(f"iteration_{iteration}")
        metric.metadata = {
            "iteration": iteration,
            "max_iterations": max_iterations,
        }

        logger.info(
            f"Iteration {iteration}/{max_iterations} started",
            extra={
                "trace_id": self.observability_manager.trace_id,
                "iteration": iteration,
                "status": "started",
            },
        )

    def on_iteration_end(self, iteration: int, state: AgentState) -> None:
        """Called when an agent iteration ends.

        Args:
            iteration: Current iteration number
            state: Current agent state
        """
        if not self.active_trace or not self.active_trace.metrics:
            return

        # Update the last metric (current iteration)
        metric = self.active_trace.metrics[-1]
        metric.complete(status=state.status.value)
        metric.metadata.update({
            "tools_called": len(state.tool_results),
            "messages": len(state.messages),
        })

        logger.info(
            f"Iteration {iteration} ended",
            extra={
                "trace_id": self.observability_manager.trace_id,
                "iteration": iteration,
                "duration_ms": int(metric.duration_ms or 0),
                "status": state.status.value,
            },
        )

    def on_tool_start(self, tool_name: str, tool_input: dict[str, Any]) -> None:
        """Called when a tool starts execution.

        Args:
            tool_name: Name of the tool
            tool_input: Input to the tool
        """
        if not self.active_trace:
            return

        metric = self.active_trace.add_metric(f"tool_{tool_name}")
        metric.metadata = {
            "tool_name": tool_name,
            "input_keys": list(tool_input.keys()),
        }

        logger.info(
            f"Tool {tool_name} started",
            extra={
                "trace_id": self.observability_manager.trace_id,
                "tool_name": tool_name,
                "status": "started",
            },
        )

    def on_tool_end(self, tool_result: ToolResult) -> None:
        """Called when a tool execution ends.

        Args:
            tool_result: Result from tool execution
        """
        if not self.active_trace or not self.active_trace.metrics:
            return

        # Update the last metric (current tool)
        metric = self.active_trace.metrics[-1]
        metric.complete(status="success" if tool_result.success else "error", error=tool_result.error)
        metric.metadata.update({
            "success": tool_result.success,
            "output_length": len(tool_result.output) if tool_result.output else 0,
        })

        logger.info(
            f"Tool {tool_result.tool_name} completed",
            extra={
                "trace_id": self.observability_manager.trace_id,
                "tool_name": tool_result.tool_name,
                "execution_time": int(tool_result.execution_time * 1000),
                "status": "success" if tool_result.success else "error",
            },
        )

    def on_agent_end(self, final_state: AgentState, status: str = "success") -> None:
        """Called when agent execution ends.

        Args:
            final_state: Final agent state
            status: Execution status (success, error, etc.)
        """
        self.observability_manager.end_trace(status)

        logger.info(
            f"Agent execution completed",
            extra={
                "trace_id": self.observability_manager.trace_id,
                "status": status,
                "iterations": final_state.iteration_count,
                "tools_used": len(final_state.tool_results),
                "duration_ms": int((self.active_trace.duration_ms or 0)),
            },
        )

    def on_error(self, error: Exception) -> None:
        """Called when an error occurs.

        Args:
            error: The exception that occurred
        """
        self.observability_manager.end_trace("error")

        logger.error(
            f"Agent execution failed: {str(error)}",
            extra={
                "trace_id": self.observability_manager.trace_id,
                "status": "error",
            },
            exc_info=True,
        )

    def get_trace(self) -> Optional[dict[str, Any]]:
        """Get the current trace as a dictionary.

        Returns:
            Trace dictionary or None
        """
        if not self.active_trace:
            return None
        return self.active_trace.to_dict()
