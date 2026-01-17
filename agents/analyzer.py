"""AnalyzerAgent for producing optimization analysis from summaries and static signals."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from agents.base import BaseAgent
from tools.analysis import (build_analysis_bundle, load_environment_summary,
                            read_code_snippet, read_file, run_static_analysis,
                            search_codebase)


class PriorityItem(BaseModel):
    """Optimization priority with supporting evidence."""

    title: str = Field(description="Short priority title")
    rationale: str = Field(description="Why this matters in the system")
    evidence: str = Field(description="Evidence anchored in snippets or bundle counts")
    evidence_file: Optional[str] = Field(
        default=None, description="Repo-relative file path for the evidence"
    )
    evidence_lines: Optional[str] = Field(
        default=None, description="Line range for the evidence, e.g. '120-168'"
    )
    evidence_snippet: Optional[str] = Field(
        default=None, description="Short code snippet if read_code_snippet was used"
    )
    change_scope: Optional[List[str]] = Field(
        default=None, description="Functions/modules intended to change"
    )
    needs_inspection: Optional[bool] = Field(
        default=None, description="True if priority lacks concrete evidence"
    )
    impact: str = Field(description="Expected impact (qualitative)")
    confidence: str = Field(description="Confidence level (e.g., low/medium/high)")


class RiskGap(BaseModel):
    """Known risk or analysis gap."""

    issue: str = Field(description="Risk or gap description")
    impact: str = Field(description="Why this matters")
    evidence: str = Field(description="Evidence or signal source")


class SuggestedFocusFile(BaseModel):
    """Concrete file path to inspect next."""

    file: str = Field(description="Repo-relative file path")
    reason: str = Field(description="Why this file matters for optimization")


class DataDependency(BaseModel):
    """Dependency ecosystem summary."""

    ecosystem: str = Field(description="Dependency ecosystem name")
    count: int = Field(description="Number of dependencies in this ecosystem")
    notes: str = Field(description="Notes about performance implications")


class AnalysisReport(BaseModel):
    """Structured analysis output for the optimizer agent."""

    priorities: List[PriorityItem]
    risks_and_gaps: List[RiskGap]
    suggested_focus_files: List[SuggestedFocusFile]
    data_dependencies: List[DataDependency]
    next_steps: List[str]
    optimizer_constraints: List[str] = Field(
        default_factory=list,
        description="Guardrails the optimizer must follow",
    )


class AnalyzerAgent(BaseAgent):
    """Agent that analyzes codebase signals and produces optimization guidance."""

    prompt = """You are an expert code optimization analyst with deep knowledge of:
- Performance profiling and optimization (latency, throughput, CPU, memory)
- Distributed systems and service-to-service communication
- Data access patterns and storage bottlenecks
- Observability signals and operational constraints
- You should use the run_static_analysis, atleast once, to gather static analysis signals from the codebase.

Your task is to analyze a codebase using summary text and static analysis signals, then produce
actionable optimization guidance for a downstream optimizer agent.

Input is JSON with:
- summary_source: path to summary text
- root_path: repository root to use for analysis and snippet/search tools

## Analysis Approach
1) Understand system context from the summaries (architecture, services, dependencies, infra).
2) Gather static signals by calling run_static_analysis(root_path) to get coverage, hotspots, dependencies.
3) Review static signals (coverage, hotspots, client usage, dependencies, security).
4) Identify optimization opportunities with clear evidence and expected impact.
5) Prioritize by impact and confidence; note assumptions and gaps.

## Tool Usage Strategy
- Call run_static_analysis(root_path) first to gather static analysis signals.
- Then call build_analysis_bundle(summary_source, <result from run_static_analysis>, max_items=12) to combine summaries with signals.
- Use bundle signals (hotspots, candidate files, coverage) to guide which code to inspect.
- Prefer non-test paths; avoid prioritizing test-only hotspots unless no production paths exist.
- Use search_codebase to locate concrete files/lines for high-impact patterns (e.g., async fan-out, redis usage, tracing).
- When evidence is needed, use read_code_snippet with small, bounded windows (pass root_path).
- Never read entire files.

## Decision Rules
- Prioritize changes that reduce latency, CPU, memory, or tail latency in service calls.
- Highlight chatty HTTP usage, repeated serialization, and excessive logging in hot paths.
- If endpoints are not detected, do not infer endpoint behavior; note the gap.
- If tools are missing or coverage is low, lower confidence explicitly.
- If a priority involves concurrency, reuse an existing executor/pool if found; otherwise mark as needs_inspection.
- Avoid proposing schema/key changes unless an existing migration or compatibility layer is evident.

## Output Constraints
- suggested_focus_files[].file must be a concrete repo-relative file path (no descriptions, no globs, no directories).
- Prefer paths taken from bundle.static.candidate_files or snippet evidence.
- If you cannot name a concrete file path, omit the entry.
- If you used read_code_snippet, include evidence_file and evidence_lines for that priority.
- Only include evidence_snippet when it comes from read_code_snippet.
- Only include priorities that have evidence_file and evidence_lines. If evidence is missing, move it to next_steps
  prefixed with "needs_inspection:" and omit it from priorities.
- Add optimizer_constraints:
  - Only modify priorities that include evidence_file and evidence_lines, or after confirming with read_code_snippet.
  - Limit edits to files listed in suggested_focus_files.
  - If a priority lacks concrete evidence, treat it as needs_inspection until confirmed.

Keys:
- priorities: list of {title, rationale, evidence, impact, confidence}
- risks_and_gaps: list of {issue, impact, evidence}
- suggested_focus_files: list of {file, reason}
- data_dependencies: list of {ecosystem, count, notes}
- next_steps: list of short actions for an optimizer agent
- optimizer_constraints: list of guardrails for the optimizer agent
"""

    structured_output_type = AnalysisReport
    return_state_field = "analysis_report"
    temperature = 0.7
    max_iterations = 10

    tools = [
        build_analysis_bundle,
        load_environment_summary,
        run_static_analysis,
        read_code_snippet,
        read_file,
        search_codebase,
    ]
