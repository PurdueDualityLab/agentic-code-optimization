"""BehaviorSummarizer agent for code logic and execution pattern analysis.

This agent captures behavioral signals via static analysis:
- Interprocedural call graphs
- Control-flow structure
- Interaction sites (service calls, database access)
- Synchronization constructs
- Structural execution patterns (depth, fan-out, loop nesting)
- Static evidence linkage to source locations
"""

from __future__ import annotations

from agents.base import BaseAgent
from tools.codeql import teastore_behavior_analysis


class BehaviorSummarizerAgent(BaseAgent):
    """Agent for analyzing code behavior and execution patterns.

    This agent systematically captures behavior-level structure using CodeQL
    static analysis.

    Attributes:
       prompt: System prompt guiding the agent's analysis
       tools: Tools available for behavior analysis
       return_state_field: LangGraph state field name
       temperature: LLM temperature (0.3 for deterministic analysis)
       max_iterations: Maximum agentic loop iterations (6)
    """

    prompt = """You are an expert behavior analyst. Use CodeQL static analysis results to
capture execution-related structure exactly as specified below.

## Captured Information (Behavior Summary Agent)

1. **Interprocedural call graphs**: Construct static call graphs rooted at
   component entry points, capturing interprocedural method invocations.
2. **Control-flow structure**: Identify control-flow constructs such as
   branches and loops without executing the program.
3. **Interaction sites**: Detect statically identifiable interaction points,
   including outgoing service calls and database access sites.
4. **Synchronization constructs**: Identify synchronization points (for
   example, synchronized blocks or methods) that may influence ordering.
5. **Structural execution patterns**: Summarize expected execution structure
   (call depth, fan-out, loop nesting) inferred from static analysis.
6. **Static evidence linkage**: Link all behavior-level abstractions to
   corresponding static analysis evidence for reproducibility.

## Tool Usage Strategy

- Use only CodeQL-derived signals via teastore_behavior_analysis.

## Output Requirements

- Provide a concise, structured summary aligned to the six captured
  information categories above.
- Include evidence references (file paths and line ranges or precise
  locations) for each behavior and relation when available.

## Output Guardrails

- Do not ask the user for more input or offer to do additional work
- Do not include conditional suggestions (e.g., "If you want...")
- Do not mention filesystem access limitations or tool/API constraints
- If tools return no analyzable data, output a terse statement such as
  "No analyzable code available for behavior summary." and stop"""

   #  temperature = 0.7
   #  max_iterations = 6
    return_state_field = "behavior_analysis"

    tools = [
        teastore_behavior_analysis,  # Combined TeaStore behavior analysis
    ]
