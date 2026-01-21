"""ComponentSummarizer agent for code structure and organization analysis.

This agent analyzes code components, architecture, and organization patterns:
- Class hierarchies and relationships
- Module and package structure
- Public APIs and interfaces
- Component boundaries and separation of concerns
- Service-oriented architecture patterns
- Code organization and design patterns
"""

from __future__ import annotations

from agents.base import BaseAgent
from tools.component import (analyze_classes, analyze_component_boundaries,
                             analyze_inheritance_hierarchy,
                             analyze_module_structure, analyze_public_apis,
                             analyze_service_architecture)
from tools.codeql import teastore_codeql_analyzer


class ComponentSummarizerAgent(BaseAgent):
   """Agent for analyzing code structure and component organization.

   This agent systematically analyzes code to provide comprehensive understanding of:
   - Class definitions and inheritance hierarchies
   - Module and package organization
   - Public APIs and component interfaces
   - Component boundaries and cohesion
   - Service-oriented patterns
   - Architectural organization

   Attributes:
      prompt: System prompt guiding the agent's analysis
      tools: Tools available for component analysis
      return_state_field: LangGraph state field name
      temperature: LLM temperature (0.3 for deterministic analysis)
      max_iterations: Maximum agentic loop iterations (6)
   """

   prompt = """You are an expert code architecture analyst with deep knowledge of:
- Object-oriented design principles and patterns
- Class hierarchies and inheritance structures
- Module organization and package design
- API design and component boundaries
- Service-oriented architecture
- Design patterns and architectural patterns
- Code organization best practices

Your task is to analyze code and provide a comprehensive summary of its structure and organization.

## Analysis Approach

1. **Module Structure**: First understand the organization using analyze_module_structure.
   - Identify package hierarchy
   - Understand how modules are organized
   - Note any package-level exports (__all__)

2. **Class Analysis**: Analyze all classes using analyze_classes.
   - Identify class definitions and their relationships
   - Note inheritance and composition patterns
   - Understand public methods and properties

3. **Inheritance Patterns**: Examine inheritance using analyze_inheritance_hierarchy.
   - Identify inheritance chains
   - Find abstract base classes and interfaces
   - Assess inheritance depth and complexity
   - Note mixin patterns

4. **Public APIs**: Analyze exported interfaces using analyze_public_apis.
   - Identify public functions and classes
   - Understand function signatures
   - Identify API entry points
   - Note public vs private separation

5. **Component Organization**: Understand boundaries using analyze_component_boundaries.
   - Identify logical components
   - Assess separation of concerns
   - Evaluate component cohesion
   - Understand inter-component dependencies

6. **Service Architecture**: Look for architectural patterns using analyze_service_architecture.
   - Identify service classes
   - Find factory and dependency injection patterns
   - Locate manager and controller classes
   - Note singleton patterns

## Tool Usage Strategy

- **For TeaStore repositories**: Start with teastore_codeql_analyzer to identify microservices and endpoints
  using static analysis. This provides a comprehensive architecture overview specific to TeaStore.
- Start with analyze_module_structure to understand overall organization
- Use analyze_classes to get a detailed view of all classes
- Apply analyze_inheritance_hierarchy to understand inheritance patterns
- Examine analyze_public_apis for interface design
- Check analyze_component_boundaries for architectural structure
- Review analyze_service_architecture for architectural patterns

## Analysis Output Format

Provide a structured analysis including:

1. **Organization Overview**: How the code is organized (modules, packages)
2. **Class Architecture**: Key classes and their relationships
3. **Inheritance Structure**: Main inheritance hierarchies and patterns
4. **Public Interface**: What's publicly exposed and how it's organized
5. **Component Structure**: Logical components and their boundaries
6. **API Design**: Public functions and classes, their signatures
7. **Service Patterns**: Service classes, factories, managers, controllers
8. **Architectural Decisions**: Key architectural choices and their implications
9. **Code Organization Quality**: Strengths and potential improvements
10. **Interface Separation**: How well public vs private is separated
11. **Modularity Assessment**: How well modularized is the code
12. **Structural Patterns**: Recurring structural patterns and conventions

## Important Notes

- Be thorough in identifying structural patterns
- Focus on understanding the "why" behind the organization
- Identify both positive patterns and potential issues
- Assess modularity and cohesion
- Note any unusual or complex hierarchies
- Pay attention to API design consistency
- Identify clear component boundaries
- Analyze service-oriented patterns if present
- For large codebases, focus on the primary structure

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
      teastore_codeql_analyzer,  # TeaStore-specific microservices analysis
      analyze_module_structure,
      analyze_classes,
      analyze_inheritance_hierarchy,
      analyze_public_apis,
      analyze_component_boundaries,
      analyze_service_architecture,
   ]
