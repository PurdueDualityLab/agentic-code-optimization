"""Code correctness checking agents using BaseAgent inheritance.

Two-phase workflow:
1. AnalysisAgent: Analyzes code for issues and correctness
2. StructuredSummaryAgent: Produces Yes/No correctness verdict
"""

from __future__ import annotations

from typing import TypedDict

from beautilog import logger
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from agents.base import BaseAgent

# Prompts for code correctness analysis
ANALYSIS_PROMPT = """You are an expert code correctness analyzer.

Your task is to thoroughly analyze a code snippet against a problem statement.
Identify any issues, missing functionality, logic errors, or edge cases not handled.

Input:
- language: Programming language
- problem_statement: Required functionality
- code_snippet: Code to analyze

Analyze the code carefully and provide a detailed assessment:
1. Does the code implement all required functionalities?
2. Are there any logic errors or edge cases not handled?
3. What issues or concerns did you find?

Be thorough and specific in your analysis.
"""

STRUCTURED_SUMMARY_PROMPT = """You are a code correctness validator.

Based on the provided analysis, determine if the code is correct.
Output ONLY "Yes" if the code is correct, or "No" if there are issues.

Analysis: {ANALYSIS}

Output (one word only):"""


class AnalysisResult(BaseModel):
    """Detailed analysis output from AnalysisAgent."""

    analysis: str = Field(description="Detailed analysis of code correctness")


class CorrectnessVerdict(BaseModel):
    """Final correctness verdict from StructuredSummaryAgent."""

    verdict: str = Field(
        description='Correctness verdict: "Yes" if correct, "No" if issues found'
    )


class AnalysisAgent(BaseAgent):
    """Analyzes code for correctness issues and provides detailed assessment."""

    structured_output_type = AnalysisResult

    prompt = ANALYSIS_PROMPT

    return_state_field = "analysis_result"
    temperature = 0.7
    max_iterations = 10

    tools = []


class StructuredSummaryAgent(BaseAgent):
    """Validates analysis and produces a structured Yes/No correctness verdict."""

    structured_output_type = CorrectnessVerdict

    prompt = STRUCTURED_SUMMARY_PROMPT

    return_state_field = "correctness_verdict"
    temperature = 0.0  # Deterministic for verdict
    max_iterations = 5

    tools = []


class CodeCorrectnessState(TypedDict):
    """State for the code correctness checking workflow."""

    language: str
    problem_statement: str
    code_snippet: str
    analysis_result: str
    correctness_verdict: str


async def analysis_node(state: CodeCorrectnessState) -> dict:
    """PHASE 1: Run AnalysisAgent for detailed analysis.

    Analyzes code for correctness issues, logic errors, and missing functionality.

    Args:
        state: Correctness state containing code and problem statement

    Returns:
        Dictionary with analysis_result
    """
    logger.info("PHASE 1: Running AnalysisAgent")
    agent = AnalysisAgent()

    input_text = (
        f"language: {state['language']}\n"
        f"problem_statement: {state['problem_statement']}\n"
        f"code_snippet: {state['code_snippet']}"
    )

    result = await agent.run(input_text)
    logger.info("PHASE 1: Analysis complete")

    return {"analysis_result": result}


async def structured_summary_node(state: CodeCorrectnessState) -> dict:
    """PHASE 2: Run StructuredSummaryAgent for final verdict.

    Produces a Yes/No correctness verdict based on the detailed analysis.

    Args:
        state: Correctness state containing analysis_result

    Returns:
        Dictionary with correctness_verdict
    """
    logger.info("PHASE 2: Running StructuredSummaryAgent")
    agent = StructuredSummaryAgent()

    input_text = f"ANALYSIS: {state.get('analysis_result', '')}"

    result = await agent.run(input_text)
    logger.info("PHASE 2: Verdict complete")

    return {"correctness_verdict": result}


def build_code_correctness_workflow() -> CompiledStateGraph:
    """Build the code correctness checking workflow.

    Constructs a LangGraph StateGraph that orchestrates:
    1. Analysis (detailed correctness assessment)
    2. Structured Summary (Yes/No verdict)

    The workflow follows a sequential DAG:
    START → analysis → structured_summary → END

    Returns:
        Compiled LangGraph StateGraph ready for invocation
    """
    logger.info("Building code correctness workflow")
    workflow = StateGraph(CodeCorrectnessState)

    # Add nodes for each phase
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("structured_summary", structured_summary_node)

    # Define sequential edges
    workflow.add_edge(START, "analysis")
    workflow.add_edge("analysis", "structured_summary")
    workflow.add_edge("structured_summary", END)

    logger.info("Code correctness workflow graph compiled")
    return workflow.compile()


async def orchestrate_code_correctness(
    language: str,
    problem_statement: str,
    code_snippet: str,
) -> CodeCorrectnessState:
    """Run the code correctness checking workflow end-to-end.

    Executes the two-phase workflow:
    1. Analysis: Analyzes code for correctness issues
    2. Structured Summary: Produces Yes/No verdict

    Args:
        language: Programming language of the code
        problem_statement: Required functionality description
        code_snippet: Code to analyze for correctness

    Returns:
        Final workflow state containing:
        - language: Programming language
        - problem_statement: Problem description
        - code_snippet: Code analyzed
        - analysis_result: Detailed analysis
        - correctness_verdict: Yes/No verdict
    """
    logger.info("Starting code correctness checking workflow")

    workflow = build_code_correctness_workflow()

    final_state: CodeCorrectnessState = await workflow.ainvoke(
        {
            "language": language,
            "problem_statement": problem_statement,
            "code_snippet": code_snippet,
            "analysis_result": "",
            "correctness_verdict": "",
        }
    )

    logger.info("Code correctness workflow finished")
    return final_state


