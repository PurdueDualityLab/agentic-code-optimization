"""BenchmarkAgent for running external benchmark commands."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from agents.base import BaseAgent
from tools.benchmark import run_benchmark_comparison


class BenchmarkReport(BaseModel):
    """Structured output for benchmark execution results."""

    before: dict = Field(description="Benchmark result before optimization")
    after: dict = Field(description="Benchmark result after optimization")
    comparison: dict = Field(description="Comparison metrics between before and after")
    report_paths: Optional[dict] = Field(
        default=None, description="Paths to written benchmark reports if generated"
    )
    charts: Optional[dict] = Field(
        default=None, description="Chart render results if generated"
    )
    summary: str = Field(
        description="Short summary of the benchmark outcome and any errors"
    )


class BenchmarkAgent(BaseAgent):
    """Agent that executes external benchmark commands and reports results."""

    prompt = """You are an automation agent that runs benchmark commands.

Input is JSON with:
- command_env: env var for benchmark command (default: BENCHMARK_CMD)
- workdir: working directory for the command
- timeout_seconds: timeout in seconds
- output_dir: optional directory to write benchmark artifacts
- render_charts: whether to render benchmark charts (requires matplotlib)

## Workflow
1) Call run_benchmark_comparison with the provided inputs.
2) Produce a BenchmarkReport JSON response.
3) If the command errors or times out, reflect it in the summary.

## Output Constraints
- Always return a single JSON object that conforms to BenchmarkReport.
- Do not emit tool calls in the final response.
"""

    structured_output_type = BenchmarkReport
    return_state_field = "benchmark_report"

    tools = [
        run_benchmark_comparison,
    ]
