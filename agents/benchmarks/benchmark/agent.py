"""Benchmark runner agent that executes commands without an LLM."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from utils.benchmark import run_benchmark_command


class BenchmarkAgent:
    """Agent for running external benchmark commands."""

    name = "BenchmarkAgent"

    def run(
        self,
        command: str,
        output_dir: Path,
        label: str,
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> dict[str, Any]:
        """Execute benchmark and return structured results."""
        return run_benchmark_command(
            command=command,
            output_dir=output_dir,
            label=label,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )


__all__ = ["BenchmarkAgent"]
