"""AnalyzerAgent for producing optimization analysis from summaries and static signals."""

from __future__ import annotations

import json
from typing import List, Optional

from langchain.agents import create_agent
from langchain.agents.middleware.model_call_limit import ModelCallLimitMiddleware
from pydantic import BaseModel, Field

from agents.base import BaseAgent, NOTIFICATION
from tools.analysis import (
    build_analysis_bundle,
    load_environment_summary,
    load_static_analysis,
    read_code_snippet,
    search_codebase,
)


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

Your task is to analyze a codebase using summary text and static analysis signals, then produce
actionable optimization guidance for a downstream optimizer agent.

Input is JSON with:
- summary_source: path to summary text
- static_source: path to static analysis JSON
- root_path: repository root to use for snippet/search tools

## Analysis Approach
1) Understand system context from the summaries (architecture, services, dependencies, infra).
2) Review static signals (coverage, hotspots, client usage, dependencies, security).
3) Identify optimization opportunities with clear evidence and expected impact.
4) Prioritize by impact and confidence; note assumptions and gaps.

## Tool Usage Strategy
- Call build_analysis_bundle(summary_source, static_source, max_items=12) first.
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

Output: JSON only, no prose.
Keys:
- priorities: list of {title, rationale, evidence, impact, confidence}
- risks_and_gaps: list of {issue, impact, evidence}
- suggested_focus_files: list of {file, reason}
- data_dependencies: list of {ecosystem, count, notes}
- next_steps: list of short actions for an optimizer agent
- optimizer_constraints: list of guardrails for the optimizer agent
"""

    return_state_field = "analysis_report"
    temperature = 0.7
    max_iterations = 20

    tools = [
        build_analysis_bundle,
        load_environment_summary,
        load_static_analysis,
        read_code_snippet,
        search_codebase,
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

        required_constraints = [
            "Only modify priorities that include evidence_file and evidence_lines, or after confirming with read_code_snippet.",
            "Limit edits to files listed in suggested_focus_files.",
            "If a priority lacks concrete evidence, treat it as needs_inspection until confirmed.",
        ]
        if isinstance(payload, dict):
            priorities = payload.get("priorities")
            next_steps = payload.get("next_steps")
            missing_titles: List[str] = []
            if isinstance(priorities, list):
                kept = []
                for item in priorities:
                    if not isinstance(item, dict):
                        continue
                    evidence_file = item.get("evidence_file")
                    evidence_lines = item.get("evidence_lines")
                    if not evidence_file or not evidence_lines:
                        item["needs_inspection"] = True
                        title = str(item.get("title") or "").strip()
                        if title:
                            missing_titles.append(title)
                        continue
                    item["needs_inspection"] = False
                    kept.append(item)
                payload["priorities"] = kept

            if missing_titles:
                note = "needs_inspection: confirm before optimization — " + "; ".join(
                    missing_titles
                )
                if not isinstance(next_steps, list):
                    next_steps = []
                if note not in next_steps:
                    if len(next_steps) >= 7:
                        next_steps[-1] = note
                    else:
                        next_steps.append(note)
                payload["next_steps"] = next_steps

            existing_constraints = payload.get("optimizer_constraints") or []
            if isinstance(existing_constraints, list):

                def _constraint_category(text: str) -> str:
                    lowered = text.lower()
                    if (
                        "evidence_file" in lowered
                        or "evidence lines" in lowered
                        or "read_code_snippet" in lowered
                    ):
                        return "evidence_required"
                    if (
                        "suggested_focus_files" in lowered
                        or "limit edits to files" in lowered
                    ):
                        return "focus_files"
                    if "needs_inspection" in lowered:
                        return "needs_inspection"
                    if "public api" in lowered or "service contract" in lowered:
                        return "api_contracts"
                    if "security" in lowered or "auth" in lowered:
                        return "security_sensitive"
                    return f"other:{lowered}"

                required_by_category = {
                    "evidence_required": required_constraints[0],
                    "focus_files": required_constraints[1],
                    "needs_inspection": required_constraints[2],
                }

                kept = []
                seen_categories = set()
                for item in existing_constraints:
                    text = str(item).strip()
                    if not text:
                        continue
                    category = _constraint_category(text)
                    if category in required_by_category:
                        continue
                    if category in seen_categories:
                        continue
                    seen_categories.add(category)
                    kept.append(text)

                combined = kept + list(required_by_category.values())
                deduped = []
                seen_text = set()
                for item in combined:
                    key = str(item).strip().lower()
                    if key in seen_text:
                        continue
                    seen_text.add(key)
                    deduped.append(item)

                payload["optimizer_constraints"] = deduped

        self.final_result = json.dumps(payload, indent=2)
        return self.final_result
