"""LangGraph-based orchestrator for code summarization workflow."""

from pathlib import Path
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from agents import (BehaviorSummarizerAgent, ComponentSummarizerAgent,
                    EnvironmentSummarizerAgent)


class SummaryState(TypedDict):
    """State for summarization workflow."""

    code_path: str
    environment_summary: str
    component_summary: str
    behavior_summary: str
    skip_environment: bool


async def environment_node(state: SummaryState) -> dict:
    """Run environment summarizer."""
    agent = EnvironmentSummarizerAgent()
    result = await agent.run(state["code_path"])
    return {"environment_summary": result}


async def component_node(state: SummaryState) -> dict:
    """Run component summarizer."""
    agent = ComponentSummarizerAgent()
    result = await agent.run(state["code_path"])
    return {"component_summary": result}


async def behavior_node(state: SummaryState) -> dict:
    """Run behavior summarizer."""
    agent = BehaviorSummarizerAgent()
    result = await agent.run(state["code_path"])
    return {"behavior_summary": result}


def check_environment_runs(state: SummaryState) -> Literal["environment", END]:
    """Check if environment summarizer has been run before."""

    return END if state.get("environment_summary") else "environment"


def build_summarization_workflow() -> StateGraph:
    """Build the summarization workflow."""
    workflow = StateGraph(SummaryState)

    # Add nodes
    workflow.add_node("environment", environment_node)
    workflow.add_node("component", component_node)
    workflow.add_node("behavior", behavior_node)

    # Add edges
    workflow.add_conditional_edges(
        START,
        check_environment_runs,
        {
            "environment": "environment",
            END: END,
        },
    )
    workflow.add_edge(START, "component")
    workflow.add_edge(START, "behavior")
    workflow.add_edge("component", END)
    workflow.add_edge("behavior", END)

    return workflow.compile()


async def orchestrate_summarizers(code_path: str) -> dict:
    """Run code summarization workflow.

    Args:
        code_path: Path to code to analyze

    Returns:
        Final workflow state with all summaries
    """
    workflow = build_summarization_workflow()
    result = await workflow.ainvoke(
        {
            "code_path": code_path,
            "environment_summary": "",
            "component_summary": "",
            "behavior_summary": "",
            "skip_environment": False,
        }
    )
    return result
