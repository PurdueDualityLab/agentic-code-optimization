"""LangGraph workflow wrapper for the code correctness check agent."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.checkers.code_correctness import CodeCorrectnessCheckAgent


class CodeCorrectnessWorkflowState(TypedDict):
    """State for the code correctness workflow wrapper."""

    input_payload: str | dict[str, Any]
    output: str


def _check_node(state: CodeCorrectnessWorkflowState) -> dict[str, Any]:
    """Run the code correctness check agent."""
    agent = CodeCorrectnessCheckAgent()
    output = agent.run(state["input_payload"])
    return {"output": output}


def build_code_correctness_workflow() -> StateGraph:
    """Build the workflow wrapper around the correctness agent."""
    workflow = StateGraph(CodeCorrectnessWorkflowState)
    workflow.add_node("check", _check_node)
    workflow.add_edge(START, "check")
    workflow.add_edge("check", END)
    return workflow.compile()


def orchestrate_code_correctness_check(input_payload: str | dict[str, Any]) -> dict[str, Any]:
    """Run the code correctness workflow end-to-end."""
    workflow = build_code_correctness_workflow()
    return workflow.invoke({"input_payload": input_payload, "output": ""})


__all__ = [
    "build_code_correctness_workflow",
    "orchestrate_code_correctness_check",
]
