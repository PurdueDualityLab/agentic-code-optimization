"""LangGraph-based orchestrator for analysis workflow."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agents.analyzers import AnalyzerAgent
from static_analisis_tools.runner import run_static_analysis
from workflows.summary_orchestrator import orchestrate_summarizers


class AnalysisState(TypedDict):
    """State for analysis workflow."""

    code_path: str
    summary_text: str
    static_analysis: dict
    analysis_report: str


def summary_node(state: AnalysisState) -> dict:
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


def static_node(state: AnalysisState) -> dict:
    """Run static analysis tools."""
    static_results = run_static_analysis(state["code_path"])
    return {"static_analysis": static_results}


def analyze_node(state: AnalysisState) -> dict:
    """Run AnalyzerAgent on combined summary + static analysis."""
    agent = AnalyzerAgent()
    with tempfile.TemporaryDirectory(prefix="analysis_inputs_") as temp_dir:
        temp_path = Path(temp_dir)
        summary_path = temp_path / "summary.txt"
        static_path = temp_path / "static_analysis.json"

        summary_path.write_text(state.get("summary_text", ""), encoding="utf-8")
        static_path.write_text(json.dumps(state.get("static_analysis", {})), encoding="utf-8")

        payload = {
            "summary_source": str(summary_path),
            "static_source": str(static_path),
        }
        result = agent.run(json.dumps(payload))
    return {"analysis_report": result}


def build_analysis_workflow() -> StateGraph:
    """Build the analysis workflow."""
    workflow = StateGraph(AnalysisState)

    workflow.add_node("summary", summary_node)
    workflow.add_node("static", static_node)
    workflow.add_node("analyze", analyze_node)

    workflow.add_edge(START, "summary")
    workflow.add_edge("summary", "static")
    workflow.add_edge("static", "analyze")
    workflow.add_edge("analyze", END)

    return workflow.compile()


def orchestrate_analysis(code_path: str) -> dict:
    """Run the analysis workflow end-to-end."""
    workflow = build_analysis_workflow()
    return workflow.invoke({
        "code_path": code_path,
        "summary_text": "",
        "static_analysis": {},
        "analysis_report": "",
    })
