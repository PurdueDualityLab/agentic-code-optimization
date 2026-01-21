"""ComponentSummarizer agent for code structure and organization analysis.

This agent captures component-level structure and relationships via static analysis:
- Component inventory across abstraction levels
- Hierarchical composition (service/package/class/method)
- Exported interfaces (e.g., HTTP endpoints/public APIs)
- Static dependency relations
- Component responsibilities inferred from structure and interactions
- Evidence mapping to source locations
"""

from __future__ import annotations

from agents.base import BaseAgent
from tools.codeql import teastore_component_analysis


class ComponentSummarizerAgent(BaseAgent):
   """Agent for analyzing code structure and component organization.

   This agent systematically captures component structure and relationships using
   CodeQL static analysis.

   Attributes:
      prompt: System prompt guiding the agent's analysis
      tools: Tools available for component analysis
      return_state_field: LangGraph state field name
      temperature: LLM temperature (0.3 for deterministic analysis)
      max_iterations: Maximum agentic loop iterations (6)
   """

   prompt = """You are an expert component analyst. Use CodeQL static analysis results to
capture component structure and relationships exactly as specified below.

## Captured Information (Component Summary Agent)

1. **Component inventory**: Identify components across abstraction levels
   (functions, classes, packages, services) from static structure.
2. **Hierarchical composition**: Derive parent-child relationships among
   components (service -> package -> class -> method).
3. **Exported interfaces**: Identify externally visible entry points such as
   HTTP endpoints or public APIs.
4. **Static dependency relations**: Extract dependency relationships among
   components (call-based, type-based, resource-based), aggregated at
   different abstraction levels.
5. **Component responsibilities**: Summarize each component's role by combining
   structure, exported interfaces, and interaction patterns.
6. **Evidence mapping**: Associate each component and relation with precise
   source locations from static analysis.

## Tool Usage Strategy

- Use only CodeQL-derived signals via teastore_component_analysis.

## Output Requirements

- Provide a concise, structured summary aligned to the six captured
  information categories above.
- Include evidence references (file paths and line ranges or precise
  locations) for each component and relation when available.

## Output Guardrails

- Do not ask the user for more input or offer to do additional work
- Do not include conditional suggestions (e.g., "If you want...")
- Do not mention filesystem access limitations or tool/API constraints
- If tools return no analyzable data, output a terse statement such as
  "No analyzable code available for component summary." and stop"""

   temperature = 0.3
   max_iterations = 6
   return_state_field = "component_analysis"

   tools = [
      teastore_component_analysis,  # Combined TeaStore component analysis
   ]
