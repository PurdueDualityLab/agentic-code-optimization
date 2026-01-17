"""LangGraph orchestrator for benchmark + summary + static + optimize + correctness + benchmark."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.analyzers import AnalyzerAgent
from agents.benchmarks import BenchmarkAgent
from agents.checkers.code_correctness import CodeCorrectnessCheckAgent
from agents.optimizers import OptimizerAgent
from static_analisis_tools.runner import run_static_analysis
from utils.benchmark import (compare_benchmark_metrics,
                             render_benchmark_charts, write_benchmark_report)
from workflows.summary_orchestrator import orchestrate_summarizers


class OptimizationCorrectnessState(TypedDict):
    """State for optimization + correctness workflow."""

    code_path: str
    analysis_source: str
    benchmark_cmd: str
    benchmark_timeout: Optional[int]
    benchmark_artifact_dir: str
    benchmark_enabled: bool
    spec: str
    mode: str
    language: str
    change_index: Optional[int]
    use_diff: bool
    summary_text: str
    static_analysis: dict
    analysis_report: str
    optimization_report: str
    correctness_report: str
    benchmark_before: dict
    benchmark_after: dict
    benchmark_report: str


def benchmark_before_node(state: OptimizationCorrectnessState) -> dict[str, Any]:
    """Run baseline benchmark before optimization."""
    if not state.get("benchmark_enabled", True):
        return {"benchmark_before": {"status": "skipped", "reason": "benchmark_disabled"}}

    command = state.get("benchmark_cmd") or ""
    if not command:
        return {"benchmark_before": {"error": "missing_benchmark_cmd"}}

    artifact_dir = Path(state.get("benchmark_artifact_dir") or "")
    benchmark_dir = artifact_dir / "benchmark" if artifact_dir else Path.cwd() / "benchmark"
    agent = BenchmarkAgent()
    result = agent.run(
        command=command,
        output_dir=benchmark_dir,
        label="before",
        cwd=state.get("code_path"),
        timeout=state.get("benchmark_timeout"),
    )
    return {"benchmark_before": result}


def summary_node(state: OptimizationCorrectnessState) -> dict[str, Any]:
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


def static_node(state: OptimizationCorrectnessState) -> dict[str, Any]:
    """Run static analysis tools."""
    static_results = run_static_analysis(state["code_path"])
    return {"static_analysis": static_results}


def analysis_node(state: OptimizationCorrectnessState) -> dict[str, Any]:
    """Run AnalyzerAgent on summary + static analysis."""
    analysis_source = state.get("analysis_source") or ""
    if analysis_source:
        path = Path(analysis_source)
        if path.exists():
            return {"analysis_report": path.read_text(encoding="utf-8", errors="ignore")}

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
            "root_path": state["code_path"],
        }
        result = agent.run(json.dumps(payload))
    return {"analysis_report": result}


def optimize_node(state: OptimizationCorrectnessState) -> dict[str, Any]:
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


def _auto_spec(change: dict, target_file: str) -> str:
    summary = str(change.get("summary", "")).strip()
    if summary:
        return (
            "Verify that the code implements the following intent without changing external behavior: "
            + summary
        )
    if target_file:
        return f"Verify that the code in {target_file} preserves existing behavior and interfaces."
    return "Verify that the code snippet preserves existing behavior and interfaces."


def correctness_node(state: OptimizationCorrectnessState) -> dict[str, Any]:
    """Run code correctness checks for applied changes."""
    report_text = state.get("optimization_report", "")
    try:
        report_data = json.loads(report_text)
    except Exception:
        return {"correctness_report": json.dumps({"error": "invalid_optimization_report"}, indent=2)}

    applied_changes = report_data.get("applied_changes", []) if isinstance(report_data, dict) else []
    if not applied_changes:
        return {"correctness_report": json.dumps({"message": "no_applied_changes"}, indent=2)}

    change_index = state.get("change_index")
    if change_index is not None:
        if change_index < 0 or change_index >= len(applied_changes):
            return {
                "correctness_report": json.dumps(
                    {"error": "change_index_out_of_range", "count": len(applied_changes)},
                    indent=2,
                )
            }
        change_indices = [change_index]
    else:
        change_indices = list(range(len(applied_changes)))

    agent = CodeCorrectnessCheckAgent()
    repo_path = Path(state["code_path"])
    spec_override = state.get("spec", "")
    mode = state.get("mode", "analyze_then_summarize")
    language = state.get("language", "C++")
    use_diff = bool(state.get("use_diff"))

    results = []
    for idx in change_indices:
        change = applied_changes[idx]
        target_file = str(change.get("file", "")).strip()
        diff_snippet = str(change.get("diff", "")).strip()

        effective_spec = spec_override or _auto_spec(change, target_file)

        code_snippet = ""
        if target_file and not use_diff:
            target_path = repo_path / target_file
            if target_path.exists():
                code_snippet = target_path.read_text(encoding="utf-8", errors="ignore")

        if not code_snippet:
            code_snippet = diff_snippet

        if not code_snippet:
            results.append({
                "change_index": idx,
                "file": target_file or None,
                "output": "",
                "error": "missing_code_snippet",
                "spec": effective_spec,
            })
            continue

        check_payload = {
            "mode": mode,
            "language": language,
            "problem_statement": effective_spec,
            "code_snippet": code_snippet,
            "strict_output_only": True,
        }
        output = agent.run(check_payload)
        results.append({
            "change_index": idx,
            "file": target_file or None,
            "output": output,
            "spec": effective_spec,
        })

    overall = None
    if mode == "analyze_then_summarize":
        overall = "Yes" if all(item.get("output") == "Yes" for item in results) else "No"

    payload = {
        "checked_files": [item.get("file") for item in results],
        "mode": mode,
        "language": language,
        "correctness_results": results,
        "correctness_overall": overall,
    }
    return {"correctness_report": json.dumps(payload, indent=2)}


def benchmark_after_node(state: OptimizationCorrectnessState) -> dict[str, Any]:
    """Run benchmark after correctness check."""
    if not state.get("benchmark_enabled", True):
        return {"benchmark_after": {"status": "skipped", "reason": "benchmark_disabled"}}

    command = state.get("benchmark_cmd") or ""
    if not command:
        return {"benchmark_after": {"error": "missing_benchmark_cmd"}}

    artifact_dir = Path(state.get("benchmark_artifact_dir") or "")
    benchmark_dir = artifact_dir / "benchmark" if artifact_dir else Path.cwd() / "benchmark"
    agent = BenchmarkAgent()
    result = agent.run(
        command=command,
        output_dir=benchmark_dir,
        label="after",
        cwd=state.get("code_path"),
        timeout=state.get("benchmark_timeout"),
    )
    return {"benchmark_after": result}


def benchmark_compare_node(state: OptimizationCorrectnessState) -> dict[str, Any]:
    """Compare benchmark results and render charts."""
    if not state.get("benchmark_enabled", True):
        payload = {
            "status": "skipped",
            "reason": "benchmark_disabled",
            "before": state.get("benchmark_before") or {},
            "after": state.get("benchmark_after") or {},
        }
        return {"benchmark_report": json.dumps(payload, indent=2)}

    before = state.get("benchmark_before") or {}
    after = state.get("benchmark_after") or {}

    comparison = compare_benchmark_metrics(before, after)
    artifact_dir = Path(state.get("benchmark_artifact_dir") or "")
    benchmark_dir = artifact_dir / "benchmark" if artifact_dir else Path.cwd() / "benchmark"
    files = write_benchmark_report(benchmark_dir, before, after, comparison)
    charts = render_benchmark_charts(benchmark_dir, comparison, before, after)

    payload = {
        "before": before,
        "after": after,
        "comparison": comparison,
        "files": files,
        "charts": charts,
    }
    return {"benchmark_report": json.dumps(payload, indent=2)}


def build_optimization_correctness_workflow() -> StateGraph:
    """Build the optimization + correctness workflow."""
    workflow = StateGraph(OptimizationCorrectnessState)
    workflow.add_node("benchmark_before", benchmark_before_node)
    workflow.add_node("summary", summary_node)
    workflow.add_node("static", static_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("optimize", optimize_node)
    workflow.add_node("correctness", correctness_node)
    workflow.add_node("benchmark_after", benchmark_after_node)
    workflow.add_node("benchmark_compare", benchmark_compare_node)

    workflow.add_edge(START, "benchmark_before")
    workflow.add_edge("benchmark_before", "summary")
    workflow.add_edge("summary", "static")
    workflow.add_edge("static", "analysis")
    workflow.add_edge("analysis", "optimize")
    workflow.add_edge("optimize", "correctness")
    workflow.add_edge("correctness", "benchmark_after")
    workflow.add_edge("benchmark_after", "benchmark_compare")
    workflow.add_edge("benchmark_compare", END)

    return workflow.compile()


def orchestrate_optimization_correctness(
    code_path: str,
    analysis_source: str = "",
    benchmark_cmd: str = "",
    benchmark_timeout: Optional[int] = None,
    benchmark_artifact_dir: str = "",
    benchmark_enabled: bool = True,
    spec: str = "",
    mode: str = "analyze_then_summarize",
    language: str = "C++",
    change_index: Optional[int] = None,
    use_diff: bool = False,
) -> dict[str, Any]:
    """Run the optimization + correctness workflow end-to-end."""
    workflow = build_optimization_correctness_workflow()
    return workflow.invoke({
        "code_path": code_path,
        "analysis_source": analysis_source,
        "benchmark_cmd": benchmark_cmd,
        "benchmark_timeout": benchmark_timeout,
        "benchmark_artifact_dir": benchmark_artifact_dir,
        "benchmark_enabled": benchmark_enabled,
        "spec": spec,
        "mode": mode,
        "language": language,
        "change_index": change_index,
        "use_diff": use_diff,
        "summary_text": "",
        "static_analysis": {},
        "analysis_report": "",
        "optimization_report": "",
        "correctness_report": "",
        "benchmark_before": {},
        "benchmark_after": {},
        "benchmark_report": "",
    })


__all__ = [
    "build_optimization_correctness_workflow",
    "orchestrate_optimization_correctness",
]
