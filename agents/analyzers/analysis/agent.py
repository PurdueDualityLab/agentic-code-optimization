"""AnalyzerAgent for producing optimization analysis from summaries and static signals."""

from __future__ import annotations

import json
from typing import List

from langchain.agents import create_agent
from langchain.agents.middleware.model_call_limit import ModelCallLimitMiddleware
from pydantic import BaseModel, Field

from agents.base import BaseAgent, NOTIFICATION
from tools.analysis import (
    build_analysis_bundle,
    load_environment_summary,
    load_static_analysis,
    read_code_snippet,
)


class PriorityItem(BaseModel):
    """Optimization priority with supporting evidence."""

    title: str = Field(description="Short priority title")
    rationale: str = Field(description="Why this matters in the system")
    evidence: str = Field(description="Evidence anchored in snippets or bundle counts")
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


class AnalyzerAgent(BaseAgent):
    """Agent that analyzes codebase signals and produces optimization guidance."""

    prompt = """You are an expert code optimization analyst with deep knowledge of:
- Performance profiling and optimization (latency, throughput, CPU, memory)
- Distributed systems and service-to-service communication
- Data access patterns and storage bottlenecks
- Observability signals and operational constraints

Your task is to analyze a codebase using summary text and static analysis signals, then produce
actionable optimization guidance for a downstream optimizer agent.

## Analysis Approach
1) Understand system context from the summaries (architecture, services, dependencies, infra).
2) Review static signals (coverage, hotspots, client usage, dependencies, security).
3) Identify optimization opportunities with clear evidence and expected impact.
4) Prioritize by impact and confidence; note assumptions and gaps.

## Tool Usage Strategy
- Call build_analysis_bundle(summary_source, static_source, max_items=20) first.
- Use bundle signals (hotspots, candidate files, coverage) to guide which code to inspect.
- Prefer non-test paths; avoid prioritizing test-only hotspots unless no production paths exist.
- When evidence is needed, use read_code_snippet with small, bounded windows.
- Never read entire files.

## Decision Rules
- Prioritize changes that reduce latency, CPU, memory, or tail latency in service calls.
- Highlight chatty HTTP usage, repeated serialization, and excessive logging in hot paths.
- Only propose security-related work if bundle.security_summary.total > 0.
- If endpoints are not detected, do not infer endpoint behavior; note the gap.
- If tools are missing or coverage is low, lower confidence explicitly.
- Do not include profiling/tracing in priorities; keep it in next_steps unless there is no other actionable evidence.
- Treat bundle.static.repository.language_counts as file counts, not lines of code.

## Output Constraints
- suggested_focus_files[].file must be a concrete repo-relative file path (no descriptions, no globs, no directories).
- Prefer paths taken from bundle.static.candidate_files or snippet evidence.
- If you cannot name a concrete file path, omit the entry.

Output: JSON only, no prose.
Keys:
- priorities: list of {title, rationale, evidence, impact, confidence}
- risks_and_gaps: list of {issue, impact, evidence}
- suggested_focus_files: list of {file, reason}
- data_dependencies: list of {ecosystem, count, notes}
- next_steps: list of short actions for an optimizer agent
"""

    return_state_field = "analysis_report"
    temperature = 0.7
    max_iterations = 6

    tools = [
        build_analysis_bundle,
        load_environment_summary,
        load_static_analysis,
        read_code_snippet,
    ]

    def run(self, input_text: str) -> str:
        """Execute the analyzer using structured output."""
        self.logger.info("Starting agent execution (structured output)")
        self.logger.info(f"Input length: {len(input_text)} characters")
        self.logger.info(f"Available tools: {list(self.tools_by_name.keys())}")
        self.logger.log(NOTIFICATION, f"Input text: {input_text[:200]}...")

        middleware = [ModelCallLimitMiddleware(run_limit=self.max_iterations)]
        agent_graph = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=self.prompt,
            response_format=AnalysisReport,
            middleware=middleware,
            name=self.name,
        )

        result = agent_graph.invoke(
            {
                "messages": [{"role": "user", "content": input_text}],
            }
        )

        self.messages = result.get("messages", [])
        structured = result.get("structured_response")
        if isinstance(structured, BaseModel):
            payload = structured.model_dump()
        else:
            payload = structured

        if payload is None:
            last_message = self.messages[-1] if self.messages else None
            payload = {
                "raw_response": (
                    getattr(last_message, "content", "") if last_message else ""
                )
            }

        self.final_result = json.dumps(payload, indent=2)
        return self.final_result
