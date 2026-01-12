"""Run directory management for agent execution logs and artifacts."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from beautilog import logger


class RunManager:
    """Manages run directories with timestamps and complete artifact management."""

    def __init__(self, base_dir: Path | str = "runs"):
        """Initialize run manager.

        Args:
            base_dir: Base directory for all runs (default: "runs")
        """
        self.base_dir = Path(base_dir)
        self.current_run_dir: Optional[Path] = None
        self.current_run_timestamp: Optional[str] = None

    def create_run_dir(self, repo_path: str, agent_name: str) -> Path:
        """Create a new run directory with timestamp.

        Args:
            repo_path: Path to the repository being analyzed
            agent_name: Name of the agent being executed

        Returns:
            Path to the created run directory
        """
        repo_name = Path(repo_path).name or "project"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = f"{agent_name}_{timestamp}"

        run_dir = self.base_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        self.current_run_dir = run_dir
        self.current_run_timestamp = timestamp

        logger.info(f"Created run directory: {run_dir}")
        return run_dir

    def save_config(self, config_src: Path | str) -> Path:
        """Copy config.ini to run directory.

        Args:
            config_src: Source path to config.ini

        Returns:
            Path to saved config file in run directory
        """
        if not self.current_run_dir:
            raise RuntimeError("No active run directory. Call create_run_dir first.")

        config_src = Path(config_src)
        config_dst = self.current_run_dir / "config.ini"

        if config_src.exists():
            shutil.copy(config_src, config_dst)
            logger.info(f"Saved config to {config_dst}")
        else:
            logger.warning(f"Config file not found: {config_src}")

        return config_dst

    def save_input(self, repo_path: str, agent_name: str) -> Path:
        """Save input parameters to input.txt.

        Args:
            repo_path: Path to the repository being analyzed
            agent_name: Name of the agent

        Returns:
            Path to saved input file
        """
        if not self.current_run_dir:
            raise RuntimeError("No active run directory. Call create_run_dir first.")

        input_data = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "repository_path": str(Path(repo_path).absolute()),
            "repository_name": Path(repo_path).name or "project",
            "working_directory": str(Path.cwd()),
        }

        input_file = self.current_run_dir / "input.txt"
        with open(input_file, "w") as f:
            for key, value in input_data.items():
                f.write(f"{key}: {value}\n")

        logger.info(f"Saved input parameters to {input_file}")
        return input_file

    def save_response(self, result: str) -> Path:
        """Save agent response to response.txt.

        Args:
            result: Agent result string

        Returns:
            Path to saved response file
        """
        if not self.current_run_dir:
            raise RuntimeError("No active run directory. Call create_run_dir first.")

        response_file = self.current_run_dir / "response.txt"
        with open(response_file, "w") as f:
            f.write(result if result else "")

        logger.info(f"Saved response to {response_file}")
        return response_file

    def save_metrics(self, metrics: dict[str, Any]) -> Path:
        """Save execution metrics to metrics.json.

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

    def save_state(self, agent: Any) -> Path:
        """Save agent state to state.json.

        Args:
            agent: The executed agent instance

        Returns:
            Path to saved state file
        """
        if not self.current_run_dir:
            raise RuntimeError("No active run directory. Call create_run_dir first.")

        langgraph_output = agent.get_langgraph_output()
        state_data = {
            "return_state_field": agent.return_state_field,
            "output": langgraph_output,
            "message_count": len(agent.messages),
            "tools_used_names": agent.tools_used_names,
        }

        state_file = self.current_run_dir / "state.json"
        with open(state_file, "w") as f:
            json.dump(state_data, f, indent=2, default=str)

        logger.info(f"Saved state to {state_file}")
        return state_file

    def save_summary(self, agent: Any, result: str, execution_time: float) -> Path:
        """Save execution summary to summary.md.

        Args:
            agent: The executed agent instance
            result: Agent result string
            execution_time: Time taken for execution in seconds

        Returns:
            Path to saved summary file
        """
        if not self.current_run_dir:
            raise RuntimeError("No active run directory. Call create_run_dir first.")

        metrics = {
            "llm_iterations": agent.iteration_count,
            "tools_used_total": agent.tools_used_count,
            "unique_tools_used": len(agent.tools_used_names),
            "tools_list": agent.tools_used_names,
            "result_length": len(result) if result else 0,
            "execution_time_seconds": execution_time,
            "max_iterations": agent.max_iterations,
            "temperature": agent.temperature,
            "provider": agent.llm.__class__.__name__,
        }

        summary_file = self.current_run_dir / "summary.md"
        with open(summary_file, "w") as f:
            f.write("# Execution Summary\n\n")
            f.write(f"**Timestamp:** {datetime.now().isoformat()}\n\n")
            f.write(f"**Agent:** {agent.name}\n\n")
            f.write(f"## Metrics\n\n")
            for key, value in metrics.items():
                f.write(f"- **{key}:** {value}\n")
            f.write(f"\n## Results\n\n")
            f.write(f"Result length: {len(result) if result else 0} characters\n")

        logger.info(f"Saved summary to {summary_file}")
        return summary_file

    def get_run_info(self) -> dict[str, Any]:
        """Get information about current run.

        Returns:
            Dictionary with run information
        """
        if not self.current_run_dir:
            raise RuntimeError("No active run directory.")

        return {
            "run_dir": str(self.current_run_dir),
            "timestamp": self.current_run_timestamp,
            "created_at": datetime.fromtimestamp(self.current_run_dir.stat().st_ctime).isoformat(),
            "artifacts": sorted([f.name for f in self.current_run_dir.glob("*")]),
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
