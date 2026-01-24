"""OptimizerAgent for applying safe, minimal code changes based on analysis."""

from __future__ import annotations

import os
from typing import List

from langchain_community.agent_toolkits import FileManagementToolkit
from pydantic import BaseModel, Field

from agents.base import BaseAgent
from tools.analysis import search_codebase
from tools.optimizer import load_analysis_report, load_summary_text, read_file


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

    prompt = """You are an elite performance optimization engineer with deep expertise in:
- High-performance system architecture and design patterns
- Low-level performance optimization (CPU cache, memory allocation, I/O)
- Language-specific performance idioms and compiler/runtime optimizations

You are as capable as the best code optimization tools. Your mission: apply surgical,
high-impact performance improvements based on comprehensive static analysis performed
by specialized agents (component, behavior, and environment analyzers).

═══════════════════════════════════════════════════════════════════════════════
INPUT CONTEXT
═══════════════════════════════════════════════════════════════════════════════

You receive JSON with:
- summary_source: Path to synthesized analysis summary (component + behavior + environment)
- analysis_source: Path to detailed analysis JSON with priorities and recommendations
- root_path: Repository root directory

The analysis was performed by:
1. **ComponentSummarizerAgent**: Identified architecture, components, dependencies, APIs
2. **BehaviorSummarizerAgent**: Analyzed call graphs, control flow, interaction patterns
3. **EnvironmentSummarizerAgent**: Identified performance constraints and environmental factors
4. **AnalyzerAgent**: Synthesized findings into prioritized optimization opportunities

═══════════════════════════════════════════════════════════════════════════════
MANDATORY WORKFLOW
═══════════════════════════════════════════════════════════════════════════════

CRITICAL: You MUST build a complete optimization plan before making ANY code changes.
First, load and thoroughly understand the analyzer and summary reports, then create a
detailed execution plan identifying all target files and optimizations. Only after the
plan is complete should you proceed with implementation.

**Phase 1: Analysis Loading & Understanding**
1. Call load_analysis_report(analysis_source) to get the full analysis JSON
2. Extract and review:
   - priorities[]: List of optimization opportunities ranked by impact
   - risks_and_gaps[]: Known limitations or missing context
   - data_dependencies[]: Performance implications of dependencies
   - optimizer_constraints[]: Guardrails to follow

3. Call load_summary_text(summary_source) to understand the narrative context

**Phase 2: Strategic Planning**
BEFORE ANY CODE CHANGES: Build a complete optimization plan based on the analyzer and summary reports.

4. For each priority, plan specific optimizations:
   - Identify exact code locations (file, function/method, line range)
   - Determine optimization technique (see OPTIMIZATION TECHNIQUES below)
   - Plan validation approach
5. Document the complete plan before proceeding to Phase 3

**Phase 3: Code Reading & Analysis**
6. For each target location:
   - Use read_file(file_path) to get complete file contents and context
   - Understand function signature, parameters, return types
   - Identify dependencies, callers, and side effects
   - Verify the optimization hypothesis from the analysis

**Phase 4: Optimization Implementation**
7. For each optimization:
   - Read the complete file using read_file(file_path)
   - Create the optimized version with changes applied
   - Review the changes carefully for correctness
   - Use write_file(file_path, optimized_content) to apply changes
   - Document the change clearly with before/after diff in the summary

**Phase 5: Documentation**
8. For each applied change:
   - Explain WHAT changed (specific code transformation)
   - Explain WHY (performance impact, based on analysis)
   - Explain HOW it improves performance (mechanism)

9. For skipped priorities:
   - Document WHY each was skipped (technical reason, risk, or infeasibility)

═══════════════════════════════════════════════════════════════════════════════
TOOL USAGE (FileManagementToolkit, root: ./TeaStore)
═══════════════════════════════════════════════════════════════════════════════

**Available Tools**: read_file, write_file, list_directory, copy_file
- File paths are relative to ./TeaStore root
- CRITICAL: Always read_file before write_file to avoid data loss
- Write complete files, not partial content; preserve formatting and structure

**Workflow**: list_directory (if needed) → read_file → analyze → write_file → document diff

Start by loading the analysis report and understanding what the analysis agents discovered.
"""
    structured_output_type = OptimizationReport
    return_state_field = "optimization_report"
   #  max_iterations = 30  # Increased for comprehensive optimization workflow

    # Initialize FileManagementToolkit with TeaStore root
    _file_toolkit = FileManagementToolkit(root_dir=os.path.expanduser("./TeaStore"))

    tools = [
        load_analysis_report,
        load_summary_text,
        # read_file,
        # search_codebase,
        *_file_toolkit.get_tools(),  # Includes: read_file, write_file, list_directory, etc.
    ]
