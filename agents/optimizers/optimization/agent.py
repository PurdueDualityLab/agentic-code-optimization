"""OptimizerAgent for applying safe, minimal code changes based on analysis."""

from __future__ import annotations

import json
from typing import List

from langchain.agents import create_agent
from langchain.agents.middleware.model_call_limit import ModelCallLimitMiddleware
from pydantic import BaseModel, Field

from agents.base import BaseAgent, NOTIFICATION
from tools.analysis import search_codebase
from tools.optimizer import (
    apply_snippet_patch_guarded,
    load_analysis_report,
    load_summary_text,
    preview_snippet_patch_guarded,
    read_code_snippet,
)


class AppliedChange(BaseModel):
    """Patch applied by the optimizer."""

    file: str = Field(description="Repo-relative path of modified file")
    summary: str = Field(description="What changed and why")
    diff: str = Field(description="Unified diff of the change")
    applied: bool = Field(description="Whether the change was applied")


class SkippedPriority(BaseModel):
    """Priority that was not modified."""

    title: str = Field(description="Priority title")
    reason: str = Field(description="Why this priority was skipped")


class OptimizationReport(BaseModel):
    """Structured optimization output."""

    applied_changes: List[AppliedChange]
    skipped_priorities: List[SkippedPriority]
    risks: List[str] = Field(description="Short risks introduced or remaining")


class OptimizerAgent(BaseAgent):
    """Agent that applies safe code optimizations based on analysis."""

    prompt = """You are a senior performance engineer and code optimizer.

Input is JSON with:
- summary_source: path to the summary text
- analysis_source: path to analysis JSON
- root_path: repository root

Your job is to safely apply code improvements without breaking behavior.

## Mandatory Workflow
1) Call load_analysis_report(analysis_source) first.
2) Extract suggested_focus_files and priorities from analysis.
3) Only modify priorities with evidence_file + evidence_lines, or after confirming with read_code_snippet.
4) Limit edits to files listed in suggested_focus_files or evidence_file entries from priorities.
5) For each change, use preview_snippet_patch_guarded first, then apply_snippet_patch_guarded.

## Tool Usage Hints
- Use search_codebase to locate existing helpers (executors, pools, tracing helpers) before introducing new ones.
- Use read_code_snippet to capture full function context before editing.

## Safety Rules
- Avoid API/schema changes, protocol changes.
- If you cannot confirm a change from snippets, skip it and explain why.
- If preview_snippet_patch fails (not found or not unique), skip the priority.

## Relaxed Optimization Rules
- You may introduce small local helpers (e.g., bounded concurrency helper) inside the same file when no
  existing executor/pool is found and the change is clearly scoped.
- You may replace unbounded std::async fan-out with a bounded helper if you preserve ordering and
  error propagation (wait/get in the same sequence as before).
- Do not add new third-party dependencies; keep changes minimal and document risks.

## Output Format (JSON only)
- applied_changes: list of {file, summary, diff, applied}
- skipped_priorities: list of {title, reason}
- risks: list of short risks introduced or remaining
"""

    return_state_field = "optimization_report"
    temperature = 1
    max_iterations = 25

    tools = [
        load_analysis_report,
        load_summary_text,
        read_code_snippet,
        search_codebase,
        preview_snippet_patch_guarded,
        apply_snippet_patch_guarded,
    ]

    def run(self, input_text: str) -> str:
        """Execute the optimizer using structured output."""
        self.logger.info("Starting agent execution (structured output)")
        self.logger.info(f"Input length: {len(input_text)} characters")
        self.logger.info(f"Available tools: {list(self.tools_by_name.keys())}")
        self.logger.log(NOTIFICATION, f"Input text: {input_text[:200]}...")

        middleware = [ModelCallLimitMiddleware(run_limit=self.max_iterations)]
        agent_graph = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=self.prompt,
            response_format=OptimizationReport,
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
