"""LangGraph-based orchestrator for the complete optimization pipeline.

This module implements a four-phase iterative pipeline:
1. PHASE 1 - SUMMARIZATION: Run environment, component, and behavior summarizers in parallel
2. PHASE 2 - ANALYSIS: Analyze summaries to produce optimization guidance with static signals
3. PHASE 3 - OPTIMIZATION: Apply safe code improvements based on analysis
4. PHASE 4 - CORRECTNESS CHECK: Validate applied changes for correctness and quality
5. LOOP: Conditionally loop back to summarization or exit based on iteration count

The pipeline uses temporary files for inter-agent communication and manages state flow
through a LangGraph workflow with iterative refinement.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Literal, TypedDict

from beautilog import logger
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.analyzers.analysis.agent import AnalyzerAgent
from agents.checkers.code_correctness.agent import CodeCorrectnessCheckAgent
from agents.optimizers.optimization.agent import OptimizerAgent
from workflows.summary_orchestrator import orchestrate_summarizers

# Maximum iterations for the optimization loop
MAX_ITERATIONS = 5


class PipelineState(TypedDict):
    """State for complete optimization pipeline.

    Tracks data flow across all pipeline phases with iterative refinement:
    - Phase 1: Summarization (environment, component, behavior)
    - Phase 2: Analysis (structured optimization guidance)
    - Phase 3: Optimization (applied changes and risks)
    - Phase 4: Correctness Check (validate applied changes)
    - Loop: Conditional node decides whether to iterate or exit
    """

    code_path: str
    summary_text: str
    analysis_report: str
    optimization_report: str
    correctness_report: str
    iteration_count: int


def summary_node(state: PipelineState) -> dict:
    """PHASE 1: Run summarization workflow and combine summaries.

    Executes the summarization orchestrator in parallel and combines
    environment, component, and behavior summaries into a single text blob
    for downstream agents.

    Args:
        state: Pipeline state containing code_path

    Returns:
        Dictionary with combined summary_text and incremented iteration_count
    """
    iteration = state.get("iteration_count", 0) + 1
    logger.info(f"PHASE 1: Running summarization orchestrator (iteration {iteration}/{MAX_ITERATIONS})")
    summaries = orchestrate_summarizers(state["code_path"])

    summary_text = (
        "ENVIRONMENT SUMMARY:\n"
        f"{summaries.get('environment_summary', '')}\n\n"
        "COMPONENT SUMMARY:\n"
        f"{summaries.get('component_summary', '')}\n\n"
        "BEHAVIOR SUMMARY:\n"
        f"{summaries.get('behavior_summary', '')}\n"
    )

    logger.info(f"PHASE 1: Summarization complete ({len(summary_text)} chars)")
    return {"summary_text": summary_text, "iteration_count": iteration}


def analyze_node(state: PipelineState) -> dict:
    """PHASE 2: Run AnalyzerAgent on combined summary.

    Creates temporary files containing the combined summary text, then invokes
    the AnalyzerAgent to produce structured optimization guidance (AnalysisReport).

    The AnalyzerAgent uses these inputs to:
    - Understand system context and architecture
    - Gather static analysis signals via the run_static_analysis tool
    - Identify optimization opportunities with evidence
    - Prioritize by impact and confidence
    - Flag risks and analysis gaps

    Args:
        state: Pipeline state containing summary_text and code_path

    Returns:
        Dictionary with analysis_report (JSON string)
    """
    logger.info("PHASE 2: Running AnalyzerAgent")
    agent = AnalyzerAgent()

    with tempfile.TemporaryDirectory(prefix="analysis_inputs_") as temp_dir:
        temp_path = Path(temp_dir)
        summary_path = temp_path / "summary.txt"

        # Write summary to temporary file
        summary_path.write_text(state.get("summary_text", ""), encoding="utf-8")

        logger.info("PHASE 2: Analyzer input files created")

        # Create payload with file paths for the agent to read
        payload = {
            "summary_source": str(summary_path),
            "root_path": state["code_path"],
        }

        result = agent.run(json.dumps(payload))
        logger.info("PHASE 2: Analysis complete")

    return {"analysis_report": result}


def optimize_node(state: PipelineState) -> dict:
    """PHASE 3: Run OptimizerAgent to apply safe code improvements.

    Creates temporary files containing the analysis report and combined
    summary text, then invokes the OptimizerAgent to apply safe,
    minimal code changes based on the analysis guidance.

    The OptimizerAgent:
    - Loads the analysis report and extracts priorities
    - Inspects code via snippets to confirm changes
    - Uses preview before applying patches
    - Limits edits to focus files from the analysis
    - Tracks applied changes and skipped priorities
    - Flags remaining and introduced risks

    Args:
        state: Pipeline state containing analysis_report and summary_text

    Returns:
        Dictionary with optimization_report (JSON string)
    """
    logger.info("PHASE 3: Running OptimizerAgent")
    agent = OptimizerAgent()

    with tempfile.TemporaryDirectory(prefix="optimizer_inputs_") as temp_dir:
        temp_path = Path(temp_dir)
        analysis_path = temp_path / "analysis_report.json"
        summary_path = temp_path / "summary.txt"

        # Write analysis report and summary to temporary files
        analysis_path.write_text(state.get("analysis_report", ""), encoding="utf-8")
        summary_path.write_text(state.get("summary_text", ""), encoding="utf-8")

        logger.info("PHASE 3: Optimizer input files created")

        # Create payload with file paths for the agent to read
        payload = {
            "analysis_source": str(analysis_path),
            "summary_source": str(summary_path),
            "root_path": state["code_path"],
        }

        result = agent.run(json.dumps(payload))
        logger.info("PHASE 3: Optimization complete")

    return {"optimization_report": result}


def correctness_check_node(state: PipelineState) -> dict:
    """PHASE 4: Run CodeCorrectnessCheckAgent to validate applied changes.

    Invokes the code correctness check agent to evaluate the correctness and
    quality of the code changes applied by the optimizer. This validates that
    the optimization did not introduce bugs or break functionality.

    The CodeCorrectnessCheckAgent:
    - Analyzes code changes for correctness against the problem context
    - Identifies any inconsistencies or logic errors
    - Provides a severity assessment of any issues found
    - Guides whether further optimization iterations are needed

    Args:
        state: Pipeline state containing optimization_report and code_path

    Returns:
        Dictionary with correctness_report (JSON string)
    """
    logger.info("PHASE 4: Running CodeCorrectnessCheckAgent")
    agent = CodeCorrectnessCheckAgent()

    # Parse the optimization report to extract applied changes
    try:
        optimization_json = json.loads(state.get("optimization_report", "{}"))
        applied_changes = optimization_json.get("applied_changes", [])
    except (json.JSONDecodeError, TypeError):
        applied_changes = []

    # Format changes for correctness check
    changes_summary = "\n".join(
        [
            f"File: {change.get('file', 'Unknown')}\n"
            f"Summary: {change.get('summary', 'No summary')}\n"
            f"Applied: {change.get('applied', False)}\n"
            for change in applied_changes
        ]
    )

    # Create payload for correctness check agent
    payload = {
        "mode": "analyze_then_summarize",
        "language": "python",
        "problem_statement": (
            "Verify that the following code optimizations maintain correctness "
            "and do not introduce bugs or break existing functionality."
        ),
        "code_snippet": (
            f"Applied optimizations from repository {state['code_path']}:\n\n"
            f"{changes_summary}"
        ),
        "strict_output_only": True,
    }

    result = agent.run(payload)
    logger.info("PHASE 4: Correctness check complete")

    return {"correctness_report": result}


def should_continue_loop(state: PipelineState) -> Literal["summarization", str]:
    """Conditional node that decides whether to loop back to summarization or end.

    Evaluates the current iteration count against MAX_ITERATIONS to determine
    if the optimization pipeline should continue iterating or finish.

    Args:
        state: Pipeline state containing iteration_count

    Returns:
        "summarization" to loop back for another iteration, or END to finish
    """
    iteration = state.get("iteration_count", 0)
    if iteration < MAX_ITERATIONS:
        logger.info(
            f"Loop decision: Continue (iteration {iteration}/{MAX_ITERATIONS})"
        )
        return "summarization"
    else:
        logger.info(f"Loop decision: End (reached max iterations {MAX_ITERATIONS})")
        return END


def build_complete_pipeline() -> CompiledStateGraph:
    """Build the complete four-phase optimization pipeline with iteration loop.

    Constructs a LangGraph StateGraph that orchestrates:
    1. Summarization (parallel environment, component, behavior summaries)
    2. Analysis (structured guidance based on summaries with static signals)
    3. Optimization (apply safe code improvements)
    4. Correctness Check (validate applied changes for correctness)
    5. Loop decision (conditionally loop back to summarization or end)

    The workflow follows a sequential DAG with conditional loop:
    START → summarization → analysis → optimization → correctness_check → (loop decision) → {summarization | END}

    Returns:
        Compiled LangGraph StateGraph ready for invocation
    """
    logger.info("Building complete optimization pipeline")
    workflow = StateGraph(PipelineState)

    # Add nodes for each phase
    workflow.add_node("summarization", summary_node)
    workflow.add_node("analysis", analyze_node)
    workflow.add_node("optimization", optimize_node)
    workflow.add_node("correctness_check", correctness_check_node)

    # Define sequential edges with conditional loop
    workflow.add_edge(START, "summarization")
    workflow.add_edge("summarization", "analysis")
    workflow.add_edge("analysis", "optimization")
    workflow.add_edge("optimization", "correctness_check")
    workflow.add_conditional_edges(
        "correctness_check",
        should_continue_loop,
        {
            "summarization": "summarization",
            END: END,
        },
    )

    logger.info("Pipeline graph compiled")
    return workflow.compile()


def orchestrate_complete_pipeline(code_path: str) -> PipelineState:
    """Run the complete optimization pipeline end-to-end.

    Executes the optimization pipeline with iterative refinement:
    1. Summarization: Generates environment, component, and behavior summaries
    2. Analysis: Produces structured optimization guidance with static analysis
    3. Optimization: Applies safe code improvements
    4. Correctness Check: Validates applied changes for correctness
    5. Loop: Conditionally iterates up to MAX_ITERATIONS times

    Args:
        code_path: Path to the repository or code directory to optimize

    Returns:
        Final pipeline state containing:
        - code_path: Input repository path
        - summary_text: Combined summaries from final iteration
        - analysis_report: Structured AnalysisReport JSON from final iteration
        - optimization_report: Final OptimizationReport JSON from final iteration
        - correctness_report: Correctness check results from final iteration
        - iteration_count: Number of iterations completed
    """
    logger.info(f"Starting complete optimization pipeline for {code_path}")

    workflow = build_complete_pipeline()

    final_state: PipelineState = workflow.invoke(
        {
            "code_path": code_path,
            "summary_text": "",
            "analysis_report": "",
            "optimization_report": "",
            "correctness_report": "",
            "iteration_count": 0,
        }
    )

    logger.info("Complete optimization pipeline finished")
    return final_state
