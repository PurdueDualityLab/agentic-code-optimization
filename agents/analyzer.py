"""AnalyzerAgent for producing optimization analysis from summaries and embedded signals."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from agents.base import BaseAgent
from tools.analysis import (build_analysis_bundle, read_code_snippet,
                            read_file, search_codebase)


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
- The summaries include static signals like call graphs, hotspots, dependencies, and database calls.

Your task is to analyze a codebase using summary text that already contains static analysis signals, then produce
actionable optimization guidance for a downstream optimizer agent.

Input is JSON with:
- summary_source: path to summary text (includes static signals like call graphs, hotspots, dependencies)
- root_path: repository root to use for analysis and snippet/search tools

## Analysis Approach
1) Understand system context from the summaries (architecture, services, dependencies, infra), which include static signals.
2) Review embedded static signals (coverage, hotspots, client usage, dependencies, database calls, call graph cues).
3) Identify optimization opportunities with clear evidence and expected impact.
4) Prioritize by impact and confidence; note assumptions and gaps.

## Tool Usage Strategy
- Call build_analysis_bundle(summary_source, max_items=12) to normalize the summaries.
- Use bundle summary sections and embedded signals to guide which code to inspect.
- Prefer non-test paths; avoid prioritizing test-only hotspots unless no production paths exist.
- Use search_codebase to locate concrete files/lines for high-impact patterns (e.g., async fan-out, redis usage, tracing).
- When evidence is needed, use read_code_snippet with small, bounded windows (pass root_path).
- Never read entire files.
- Retry failed tools with updated arguements once.

## Decision Rules
- Prioritize changes that reduce latency, CPU, memory, or tail latency in service calls.
- Highlight chatty HTTP usage, repeated serialization, and excessive logging in hot paths.
- If endpoints are not detected, do not infer endpoint behavior; note the gap.
- If a priority involves concurrency, reuse an existing executor/pool if found; otherwise mark as needs_inspection.
- Avoid proposing schema/key changes unless an existing migration or compatibility layer is evident.
- Feel free to suggest restructing modules/functions for better performance if evidence supports it.
- SUggest removing nested function calls if applicable.

## Output Constraints
- suggested_focus_files[].file must be a concrete repo-relative file path (no descriptions, no globs, no directories).
- If you used read_code_snippet, include evidence_file and evidence_lines for that priority.
- Only include evidence_snippet when it comes from read_code_snippet.
  prefixed with "needs_inspection:" and omit it from priorities.
- After any tool calls, respond with a single JSON object that conforms to the AnalysisReport schema.

"""

    structured_output_type = AnalysisReport
    return_state_field = "analysis_report"
    temperature = 0.7
    max_iterations = 10

    tools = [
        build_analysis_bundle,
        read_code_snippet,
        # read_file,
        # search_codebase,
    ]
