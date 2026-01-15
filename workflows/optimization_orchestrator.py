"""LangGraph-based orchestrator for optimization workflow."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agents.optimizers import OptimizerAgent
from workflows.analysis_orchestrator import orchestrate_analysis
from workflows.summary_orchestrator import orchestrate_summarizers


class OptimizationState(TypedDict):
    """State for optimization workflow."""

    code_path: str
    analysis_source: str
    summary_text: str
    analysis_report: str
    optimization_report: str


def summary_node(state: OptimizationState) -> dict:
    """Run summarization workflow and combine summaries into a single text blob."""
    summaries = orchestrate_summarizers(state["code_path"])
    summary_text = (
        "ENVIRONMENT SUMMARY:\n"
        f"{summaries.get('environment_summary', '')}\n\n"
        "COMPONENT SUMMARY:\n"
        f"{summaries.get('component_summary', '')}\n\n"
        "BEHAVIOR SUMMARY:\n"
        f"{summaries.get('behavior_summary', '')}\n"
    )
    return {"summary_text": summary_text}


def analysis_node(state: OptimizationState) -> dict:
    """Load existing analysis or run analysis workflow."""
    analysis_source = state.get("analysis_source")
    if analysis_source:
        path = Path(analysis_source)
        if path.exists():
            return {"analysis_report": path.read_text(encoding="utf-8", errors="ignore")}

    result = orchestrate_analysis(state["code_path"])
    return {"analysis_report": result.get("analysis_report", "")}


def optimize_node(state: OptimizationState) -> dict:
    """Run OptimizerAgent on summary + analysis report."""
    agent = OptimizerAgent()
    with tempfile.TemporaryDirectory(prefix="optimization_inputs_") as temp_dir:
        temp_path = Path(temp_dir)
        summary_path = temp_path / "summary.txt"
        analysis_path = temp_path / "analysis.json"

        summary_path.write_text(state.get("summary_text", ""), encoding="utf-8")
        analysis_path.write_text(state.get("analysis_report", ""), encoding="utf-8")

        payload = {
            "summary_source": str(summary_path),
            "analysis_source": str(analysis_path),
            "root_path": state["code_path"],
        }
        result = agent.run(json.dumps(payload))
    return {"optimization_report": result}


def build_optimization_workflow() -> StateGraph:
    """Build the optimization workflow."""
    workflow = StateGraph(OptimizationState)

    workflow.add_node("summary", summary_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("optimize", optimize_node)

    workflow.add_edge(START, "summary")
    workflow.add_edge("summary", "analysis")
    workflow.add_edge("analysis", "optimize")
    workflow.add_edge("optimize", END)

    return workflow.compile()


def orchestrate_optimization(code_path: str, analysis_source: str = "") -> dict:
    """Run the optimization workflow end-to-end."""
    workflow = build_optimization_workflow()
    return workflow.invoke({
        "code_path": code_path,
        "analysis_source": analysis_source,
        "summary_text": "",
        "analysis_report": "",
        "optimization_report": "",
    })
