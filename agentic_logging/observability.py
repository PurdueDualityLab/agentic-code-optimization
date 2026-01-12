"""Observability utilities for agent execution tracing and metrics."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from agentic_logging.config import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutionMetrics:
    """Metrics for a single execution event."""

    event_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "pending"
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def complete(self, status: str = "success", error: Optional[str] = None) -> None:
        """Mark execution as complete.

        Args:
            status: Execution status (success, error, timeout, etc.)
            error: Optional error message
        """
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = status
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_name": self.event_name,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class Trace:
    """Trace for a complete agent execution."""

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    repo_path: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "running"
    metrics: list[ExecutionMetrics] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def complete(self, status: str = "success") -> None:
        """Mark trace as complete.

        Args:
            status: Final status (success, error, timeout, etc.)
        """
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = status

    def add_metric(self, event_name: str) -> ExecutionMetrics:
        """Add a new metric to the trace.

        Args:
            event_name: Name of the event

        Returns:
            ExecutionMetrics instance for tracking
        """
        metric = ExecutionMetrics(event_name=event_name, start_time=time.time())
        self.metrics.append(metric)
        return metric

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "agent_name": self.agent_name,
            "repo_path": self.repo_path,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "metrics": [m.to_dict() for m in self.metrics],
            "metadata": self.metadata,
        }

    def save_json(self, file_path: Path) -> None:
        """Save trace to JSON file.

        Args:
            file_path: Path to save trace JSON
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Trace saved to {file_path}")


class ObservabilityManager:
    """Manages tracing and metrics collection."""

    def __init__(self, trace_id: Optional[str] = None):
        """Initialize observability manager.

        Args:
            trace_id: Optional trace ID (generated if not provided)
        """
        self.trace_id = trace_id or str(uuid.uuid4())
        self.traces: dict[str, Trace] = {}
        self.active_trace: Optional[Trace] = None

    def start_trace(self, agent_name: str, repo_path: str = "") -> Trace:
        """Start a new trace.

        Args:
            agent_name: Name of the agent
            repo_path: Optional repository path being analyzed

        Returns:
            Created Trace instance
        """
        trace = Trace(
            trace_id=self.trace_id,
            agent_name=agent_name,
            repo_path=repo_path,
        )
        self.active_trace = trace
        self.traces[agent_name] = trace
        logger.info(
            f"Trace started for {agent_name}",
            extra={
                "trace_id": self.trace_id,
                "agent_name": agent_name,
                "status": "started",
            },
        )
        return trace

    def end_trace(self, status: str = "success") -> Optional[Trace]:
        """End the active trace.

        Args:
            status: Final status (success, error, timeout, etc.)

        Returns:
            Completed Trace instance
        """
        if self.active_trace:
            self.active_trace.complete(status)
            logger.info(
                f"Trace completed for {self.active_trace.agent_name}",
                extra={
                    "trace_id": self.trace_id,
                    "agent_name": self.active_trace.agent_name,
                    "status": status,
                    "duration_ms": self.active_trace.duration_ms,
                },
            )
            return self.active_trace
        return None

    def get_trace(self, agent_name: str) -> Optional[Trace]:
        """Get a trace by agent name.

        Args:
            agent_name: Name of the agent

        Returns:
            Trace instance or None
        """
        return self.traces.get(agent_name)

    def save_all_traces(self, directory: Path) -> None:
        """Save all traces to JSON files.

        Args:
            directory: Directory to save traces
        """
        directory.mkdir(parents=True, exist_ok=True)
        for agent_name, trace in self.traces.items():
            file_path = directory / f"{agent_name}_trace.json"
            trace.save_json(file_path)
