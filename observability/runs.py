"""Run directory management for agent execution logs and artifacts."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from agentic_logging import get_logger

logger = get_logger(__name__)


class RunManager:
    """Manages run directories with timestamps and artifacts."""

    def __init__(self, base_dir: Path | str = "runs"):
        """Initialize run manager.

        Args:
            base_dir: Base directory for all runs (default: "runs")
        """
        self.base_dir = Path(base_dir)
        self.current_run_dir: Optional[Path] = None
        self.trace_id: Optional[str] = None

    def create_run_dir(self, agent_name: str, trace_id: str) -> Path:
        """Create a new run directory with timestamp.

        Args:
            agent_name: Name of the agent
            trace_id: Unique trace ID for this run

        Returns:
            Path to the created run directory
        """
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        trace_short = trace_id[:8]
        run_name = f"{agent_name}_{timestamp}_{trace_short}"

        run_dir = self.base_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        self.current_run_dir = run_dir
        self.trace_id = trace_id

        logger.info(f"Created run directory: {run_dir}")
        return run_dir

    def save_config(self, config_src: Path) -> Path:
        """Copy config.ini to run directory.

        Args:
            config_src: Source path to config.ini

        Returns:
            Path to saved config file in run directory
        """
        if not self.current_run_dir:
            raise RuntimeError("No active run directory. Call create_run_dir first.")

        config_dst = self.current_run_dir / "config.ini"
        shutil.copy(config_src, config_dst)
        logger.info(f"Saved config to {config_dst}")
        return config_dst

    def save_logs(self, logs_data: list[str]) -> Path:
        """Save JSON logs to run directory.

        Args:
            logs_data: List of JSON log line strings

        Returns:
            Path to saved logs file
        """
        if not self.current_run_dir:
            raise RuntimeError("No active run directory. Call create_run_dir first.")

        logs_file = self.current_run_dir / "logs.json"
        with open(logs_file, "w") as f:
            for log_line in logs_data:
                f.write(log_line + "\n")

        logger.info(f"Saved logs to {logs_file}")
        return logs_file

    def save_metrics(self, metrics: dict[str, Any]) -> Path:
        """Save execution metrics to run directory.

        Args:
            metrics: Dictionary of metrics

        Returns:
            Path to saved metrics file
        """
        if not self.current_run_dir:
            raise RuntimeError("No active run directory. Call create_run_dir first.")

        metrics_file = self.current_run_dir / "metrics.json"
        with open(metrics_file, "w") as f:
            json.dump(metrics, f, indent=2)

        logger.info(f"Saved metrics to {metrics_file}")
        return metrics_file

    def save_state(self, state_dict: dict[str, Any]) -> Path:
        """Save agent state to run directory.

        Args:
            state_dict: Agent state dictionary

        Returns:
            Path to saved state file
        """
        if not self.current_run_dir:
            raise RuntimeError("No active run directory. Call create_run_dir first.")

        state_file = self.current_run_dir / "agent_state.json"
        with open(state_file, "w") as f:
            json.dump(state_dict, f, indent=2)

        logger.info(f"Saved agent state to {state_file}")
        return state_file

    def save_result(self, result: str) -> Path:
        """Save agent result to run directory.

        Args:
            result: Agent result string

        Returns:
            Path to saved result file
        """
        if not self.current_run_dir:
            raise RuntimeError("No active run directory. Call create_run_dir first.")

        result_file = self.current_run_dir / "result.txt"
        with open(result_file, "w") as f:
            f.write(result)

        logger.info(f"Saved result to {result_file}")
        return result_file

    def save_trace(self, trace_dict: dict[str, Any]) -> Path:
        """Save execution trace to run directory.

        Args:
            trace_dict: Trace dictionary from ObservabilityManager

        Returns:
            Path to saved trace file
        """
        if not self.current_run_dir:
            raise RuntimeError("No active run directory. Call create_run_dir first.")

        trace_file = self.current_run_dir / "trace.json"
        with open(trace_file, "w") as f:
            json.dump(trace_dict, f, indent=2)

        logger.info(f"Saved trace to {trace_file}")
        return trace_file

    def get_run_info(self) -> dict[str, Any]:
        """Get information about current run.

        Returns:
            Dictionary with run information
        """
        if not self.current_run_dir:
            raise RuntimeError("No active run directory.")

        return {
            "run_dir": str(self.current_run_dir),
            "trace_id": self.trace_id,
            "created_at": datetime.fromtimestamp(self.current_run_dir.stat().st_ctime).isoformat(),
            "artifacts": [f.name for f in self.current_run_dir.glob("*")],
        }

    def list_runs(self) -> list[dict[str, Any]]:
        """List all runs in base directory.

        Returns:
            List of run information dictionaries
        """
        if not self.base_dir.exists():
            return []

        runs = []
        for run_dir in sorted(self.base_dir.iterdir(), reverse=True):
            if run_dir.is_dir():
                runs.append({
                    "name": run_dir.name,
                    "path": str(run_dir),
                    "created_at": datetime.fromtimestamp(run_dir.stat().st_ctime).isoformat(),
                    "artifacts": len(list(run_dir.glob("*"))),
                })

        return runs
