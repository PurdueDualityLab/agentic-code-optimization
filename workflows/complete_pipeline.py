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
from typing import Any, Callable, Literal, Optional, Type, TypedDict

from beautilog import logger
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents import (AnalysisReport, AnalyzerAgent, OptimizationReport,
                    OptimizerAgent, orchestrate_code_correctness)

from .summary_orchestrator import orchestrate_summarizers

# Maximum iterations for the optimization loop
MAX_ITERATIONS = 5


class PipelinePhase:
    """Defines a phase in the optimization pipeline."""

    def __init__(
        self,
        name: str,
        node_fn: Callable[[Any], dict],
        agent_class: Optional[Type] = None,
        return_fields: Optional[list[str]] = None,
        return_class: Optional[Type] = None,
    ):
        """Initialize a pipeline phase.

        Args:
            name: Phase name (e.g., "analysis")
            node_fn: Node function to execute
            agent_class: Optional agent class (used to extract return_state_field)
            return_fields: Optional list of state fields this phase returns
            return_class: Optional Pydantic model class for structured return type
        """
        self.name = name
        self.node_fn = node_fn
        self.agent_class = agent_class
        self.return_fields = return_fields or []
        self.return_class = return_class

        # Extract return fields from agent if provided
        if agent_class:
            try:
                agent_instance = agent_class()
                if hasattr(agent_instance, "return_state_field"):
                    self.return_fields.append(agent_instance.return_state_field)
            except Exception:
                pass  # Agent may require specific init args


def build_pipeline_state(phases: list[PipelinePhase]) -> Type[TypedDict]:
    """Dynamically build PipelineState TypedDict from pipeline phases.

    Args:
        phases: List of pipeline phases

    Returns:
        A TypedDict class with state fields from all phases
    """
    state_fields: dict[str, Type] = {
        "code_path": str,
        "iteration_count": int,
    }

    # Add state fields from each phase's return fields
    for phase in phases:
        for field in phase.return_fields:
            state_fields[field] = str  # All agent outputs stored as JSON strings

    return TypedDict("PipelineState", state_fields)


# Define pipeline phases in execution order
_PIPELINE_PHASES = [
    PipelinePhase("summarization", None, return_fields=["summary_text"]),
    PipelinePhase(
        "analysis",
        None,
        agent_class=AnalyzerAgent,
        return_class=AnalysisReport,
    ),
    PipelinePhase(
        "optimization",
        None,
        agent_class=OptimizerAgent,
        return_class=OptimizationReport,
    ),
    PipelinePhase(
        "correctness_check",
        None,
        return_fields=["analysis_result", "correctness_verdict"],
        return_class=tuple,  # Composite: (AnalysisResult, CorrectnessVerdict)
    ),
]

# Dynamically build PipelineState from phase definitions
PipelineState = build_pipeline_state(_PIPELINE_PHASES)


async def summary_node(state: PipelineState) -> dict:
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
    summaries = await orchestrate_summarizers(state["code_path"])

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


async def analyze_node(state: PipelineState) -> dict:
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

        result = await agent.run(json.dumps(payload))
        logger.info("PHASE 2: Analysis complete")

    return {"analysis_report": result}


async def optimize_node(state: PipelineState) -> dict:
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

        result = await agent.run(json.dumps(payload))
        logger.info("PHASE 3: Optimization complete")

    return {"optimization_report": result}


async def correctness_check_node(state: PipelineState) -> dict:
    """PHASE 4: Run code correctness workflow.

    Orchestrates a two-phase correctness check:
    - Phase 4a: Detailed analysis of applied code changes
    - Phase 4b: Produces Yes/No correctness verdict

    Args:
        state: Pipeline state containing optimization_report

    Returns:
        Dictionary with analysis_result and correctness_verdict
    """
    logger.info("PHASE 4: Running code correctness workflow")

    # Parse the optimization report to extract applied changes
    try:
        optimization_json = json.loads(state.get("optimization_report", "{}"))
        applied_changes = optimization_json.get("applied_changes", [])
    except (json.JSONDecodeError, TypeError):
        applied_changes = []

    # Format changes for analysis
    changes_summary = "\n".join(
        [
            f"File: {change.get('file', 'Unknown')}\n"
            f"Summary: {change.get('summary', 'No summary')}\n"
            f"Applied: {change.get('applied', False)}\n"
            for change in applied_changes
        ]
    )

    code_snippet = (
        f"Applied optimizations from repository {state['code_path']}:\n\n"
        f"{changes_summary}"
    )

    # Run the code correctness workflow
    correctness_state = await orchestrate_code_correctness(
        language="python",
        problem_statement=(
            "Verify that the following code optimizations maintain correctness "
            "and do not introduce bugs or break existing functionality."
        ),
        code_snippet=code_snippet,
    )

    logger.info("PHASE 4: Code correctness workflow complete")

    return {
        "analysis_result": correctness_state.get("analysis_result", ""),
        "correctness_verdict": correctness_state.get("correctness_verdict", ""),
    }


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

    Constructs a LangGraph StateGraph from phase definitions that orchestrates:
    1. Summarization (parallel environment, component, behavior summaries)
    2. Analysis (structured guidance based on summaries with static signals)
    3. Optimization (apply safe code improvements)
    4. Correctness Check (orchestrates pain analysis and structured verdict)
    5. Loop decision (conditionally loop back to summarization or end)

    The workflow follows a sequential DAG with conditional loop:
    START → summarization → analysis → optimization → correctness_check → (loop decision) → {summarization | END}

    State fields are dynamically generated from phase definitions:
    - summarization → summary_text
    - analysis → analysis_report
    - optimization → optimization_report
    - correctness_check → pain_analysis_result, correctness_verdict

    Returns:
        Compiled LangGraph StateGraph ready for invocation
    """
    logger.info("Building complete optimization pipeline")
    workflow = StateGraph(PipelineState)

    # Map phase names to node functions
    node_functions = {
        "summarization": summary_node,
        "analysis": analyze_node,
        "optimization": optimize_node,
        "correctness_check": correctness_check_node,
    }

    # Add nodes from phase definitions
    for phase in _PIPELINE_PHASES:
        node_fn = node_functions.get(phase.name)
        if node_fn:
            workflow.add_node(phase.name, node_fn)
            logger.debug(f"Added node: {phase.name} → {phase.return_fields}")

    # Build sequential edges from phase order
    workflow.add_edge(START, _PIPELINE_PHASES[0].name)
    for i in range(len(_PIPELINE_PHASES) - 1):
        current_phase = _PIPELINE_PHASES[i]
        next_phase = _PIPELINE_PHASES[i + 1]
        workflow.add_edge(current_phase.name, next_phase.name)
        logger.debug(f"Added edge: {current_phase.name} → {next_phase.name}")

    # Add conditional loop from last phase back to first phase
    last_phase = _PIPELINE_PHASES[-1]
    first_phase = _PIPELINE_PHASES[0]
    workflow.add_conditional_edges(
        last_phase.name,
        should_continue_loop,
        {
            first_phase.name: first_phase.name,
            END: END,
        },
    )
    logger.debug(
        f"Added conditional edge: {last_phase.name} → ({first_phase.name} | END)"
    )

    logger.info("Pipeline graph compiled")
    return workflow.compile()


def _build_initial_state(code_path: str) -> dict[str, Any]:
    """Build initial state with all dynamic fields initialized.

    Args:
        code_path: Path to the repository to optimize

    Returns:
        Dictionary with all state fields initialized to empty strings/zeros
    """
    initial_state = {
        "code_path": code_path,
        "iteration_count": 0,
    }

    # Initialize all return fields from phases with empty strings
    for phase in _PIPELINE_PHASES:
        for field in phase.return_fields:
            initial_state[field] = ""

    return initial_state


async def orchestrate_complete_pipeline(code_path: str) -> PipelineState:
    """Run the complete optimization pipeline end-to-end.

    Executes the optimization pipeline with iterative refinement through dynamically
    configured phases:
    1. Summarization: Generates environment, component, and behavior summaries
    2. Analysis: Produces structured optimization guidance with static analysis
    3. Optimization: Applies safe code improvements
    4. Correctness Check: Validates applied changes for correctness and quality
    5. Loop: Conditionally iterates up to MAX_ITERATIONS times

    State fields are dynamically generated from phase definitions:
    - Phase outputs are automatically added to state based on agent.return_state_field
    - Each phase receives the updated state from all previous phases
    - Iteration count controls loop continuation

    Args:
        code_path: Path to the repository or code directory to optimize

    Returns:
        Final pipeline state containing dynamically generated fields:
        - code_path: Input repository path
        - summary_text: Combined summaries from final iteration
        - analysis_report: Structured AnalysisReport JSON from final iteration
        - optimization_report: Final OptimizationReport JSON from final iteration
        - analysis_result: Detailed correctness analysis from final iteration
        - correctness_verdict: Yes/No verdict from final iteration
        - iteration_count: Number of iterations completed
    """
    logger.info(f"Starting complete optimization pipeline for {code_path}")
    logger.info(f"Pipeline phases: {[p.name for p in _PIPELINE_PHASES]}")
    logger.info(f"Dynamic state fields: {list(PipelineState.__annotations__.keys())}")

    workflow = build_complete_pipeline()

    initial_state = _build_initial_state(code_path)
    final_state: PipelineState = await workflow.ainvoke(initial_state)

    logger.info("Complete optimization pipeline finished")
    return final_state
