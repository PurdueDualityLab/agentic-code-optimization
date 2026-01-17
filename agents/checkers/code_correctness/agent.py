"""LangGraph agent for code correctness checking with fixed CODEJUDGE prompts."""

from __future__ import annotations

import json
from typing import Any, Literal, TypedDict

from langchain.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from config import AgentConfig, ConfigParser
from providers import LLM, ProviderRegistry


PROMPT_TABLE18_ANALYSIS = """You will be provided with a problem statement and a code snippet that supposedly addresses the
problem in {LANGUAGE}.
Your task is to check if the code snippet covers the required functionalities. Do not provide a
corrected version.
Evaluation Steps:
1. Read the problem statement carefully and identify the required functionalities of the
implementation. You can refer to the example to understand the problem better.
2. Read the code snippet and analyze its logic. Check if the code snippet covers all the required
functionalities of the problem.
3. Finally, conclude your evaluation.
Problem Statement: {PROBLEM}
Code Snippet: {CODE}
<ANALYSIS>"""

PROMPT_TABLE18_SUMMARY = """You will be provided with an analysis result of a code snippet.
If the analysis believes that the code snippet is correct, output: "Yes". Otherwise, output: "No".
Analysis Result: {ANALYSIS}"""

PROMPT_TABLE19_FAULT_LOCALIZATION = """You will be provided with a problem statement, a code snippet that supposedly addresses the problem,
and a catalog of code inconsistencies.
Evaluation Steps:
1. Read the problem statement carefully to identify the functionalities required for the
implementation.
2. Read the code snippet and compare it to the problem statement. Check if the code snippet covers
the required functionalities.
3. Output your answer in a JSON format list.
a) If the code snippet is correct, output: [{"inconsistency": "None", "severity": "Negligible"}].
b) If the code snippet is incorrect, output the identified inconsistencies and their severity
according to the catalog of code inconsistencies.
Problem: {PROBLEM}
Code Snippet: {CODE}
Taxonomy of Common Inconsistencies:
1. Missing dependency declarations: Negligible
2. No error messages for unexpected input cases: Negligible
3. Inefficiency, unnecessary statements: Negligible
4. Edge case not handled: Small
5. Logic error: Major
6. Function or variable not defined: Fatal
7. Code not completed: Fatal
Evaluation Form:
JSON output (a JSON list only):
[{"inconsistency": "None", "severity": "Negligible"}]"""


class CodeCorrectnessState(TypedDict):
    """State for the code correctness check workflow."""

    mode: str
    language: str
    problem_statement: str
    code_snippet: str
    strict_output_only: bool
    analysis_output: str
    final_output: str
    error: str


class CodeCorrectnessCheckAgent:
    """LangGraph agent that evaluates code correctness using fixed prompts."""

    name = "code_correctness_check"

    def __init__(self, provider_name: str | None = None) -> None:
        config = ConfigParser.get(AgentConfig)
        self.provider_name = provider_name or config.default_provider
        self.llm = ProviderRegistry.get(self.provider_name, LLM)

    def run(self, input_payload: str | dict[str, Any]) -> str:
        """Run the correctness check workflow with wrapper-level JSON input."""
        payload = self._parse_payload(input_payload)
        workflow = self._build_workflow()
        result = workflow.invoke(payload)
        if payload["strict_output_only"]:
            return result.get("final_output", "")
        return self._rich_output(payload, result)

    def _parse_payload(self, input_payload: str | dict[str, Any]) -> CodeCorrectnessState:
        if isinstance(input_payload, str):
            try:
                payload = json.loads(input_payload)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid JSON input for code correctness check") from exc
        elif isinstance(input_payload, dict):
            payload = input_payload
        else:
            raise ValueError("Input payload must be JSON string or dict")

        mode = payload.get("mode") or "analyze_then_summarize"
        if mode not in {"analyze_then_summarize", "fault_localization"}:
            raise ValueError("Invalid mode for code correctness check")

        language = payload.get("language")
        problem_statement = payload.get("problem_statement")
        code_snippet = payload.get("code_snippet")
        strict_output_only = payload.get("strict_output_only", True)

        if not language or not problem_statement or not code_snippet:
            raise ValueError("Missing required input fields for code correctness check")

        return {
            "mode": mode,
            "language": str(language),
            "problem_statement": str(problem_statement),
            "code_snippet": str(code_snippet),
            "strict_output_only": bool(strict_output_only),
            "analysis_output": "",
            "final_output": "",
            "error": "",
        }

    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(CodeCorrectnessState)
        workflow.add_node("analysis", self._analysis_node)
        workflow.add_node("summary", self._summary_node)
        workflow.add_node("fault_localization", self._fault_localization_node)

        workflow.add_conditional_edges(
            START,
            self._route_mode,
            {
                "analysis": "analysis",
                "fault_localization": "fault_localization",
            },
        )
        workflow.add_edge("analysis", "summary")
        workflow.add_edge("summary", END)
        workflow.add_edge("fault_localization", END)
        return workflow.compile()

    def _route_mode(self, state: CodeCorrectnessState) -> Literal["analysis", "fault_localization"]:
        if state["mode"] == "fault_localization":
            return "fault_localization"
        return "analysis"

    def _analysis_node(self, state: CodeCorrectnessState) -> dict[str, Any]:
        prompt = _render_prompt(
            PROMPT_TABLE18_ANALYSIS,
            {
                "LANGUAGE": state["language"],
                "PROBLEM": state["problem_statement"],
                "CODE": state["code_snippet"],
            },
        )
        analysis_output = self._call_llm(prompt)
        return {"analysis_output": analysis_output}

    def _summary_node(self, state: CodeCorrectnessState) -> dict[str, Any]:
        prompt = _render_prompt(
            PROMPT_TABLE18_SUMMARY,
            {"ANALYSIS": state.get("analysis_output", "")},
        )
        output = self._call_llm(prompt)
        validated = _validate_yes_no(output)
        if not validated:
            output = self._call_llm(prompt)
            validated = _validate_yes_no(output)

        if not validated:
            if state["strict_output_only"]:
                raise ValueError("Invalid summary output for code correctness check")
            return {"final_output": "", "error": "invalid_summary_output"}

        return {"final_output": output.strip()}

    def _fault_localization_node(self, state: CodeCorrectnessState) -> dict[str, Any]:
        prompt = _render_prompt(
            PROMPT_TABLE19_FAULT_LOCALIZATION,
            {
                "PROBLEM": state["problem_statement"],
                "CODE": state["code_snippet"],
            },
        )
        output = self._call_llm(prompt)
        validated = _validate_json_list(output)
        if not validated:
            output = self._call_llm(prompt)
            validated = _validate_json_list(output)

        if not validated:
            if state["strict_output_only"]:
                raise ValueError("Invalid fault localization output for code correctness check")
            return {"final_output": "", "error": "invalid_fault_localization_output"}

        return {"final_output": output.strip()}

    def _call_llm(self, prompt: str) -> str:
        response = self.llm.invoke([HumanMessage(content=prompt)])
        if hasattr(response, "content"):
            return str(response.content)
        return str(response)

    def _rich_output(self, payload: CodeCorrectnessState, result: dict[str, Any]) -> str:
        output = result.get("final_output", "")
        error = result.get("error", "")
        rich = {
            "mode": payload["mode"],
            "output": output,
            "analysis_output": result.get("analysis_output", ""),
            "error": error or None,
        }
        return json.dumps(rich, indent=2)


def _render_prompt(template: str, substitutions: dict[str, str]) -> str:
    rendered = template
    for key, value in substitutions.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


def _validate_yes_no(output: str) -> bool:
    text = output.strip()
    return text in {"Yes", "No"}


def _validate_json_list(output: str) -> bool:
    text = output.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, list)


__all__ = [
    "CodeCorrectnessCheckAgent",
    "PROMPT_TABLE18_ANALYSIS",
    "PROMPT_TABLE18_SUMMARY",
    "PROMPT_TABLE19_FAULT_LOCALIZATION",
]
