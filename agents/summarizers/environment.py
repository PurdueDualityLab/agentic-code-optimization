"""EnvironmentSummarizer agent for repository structure and configuration analysis.

This agent analyzes a code repository's root directory to identify:
- Programming language(s)
- Frameworks and libraries
- Build systems and package managers
- Containerization (Docker, Kubernetes)
- Environment configuration
- Development tools and CI/CD
- Dependencies and requirements
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from agents.base import BaseAgent
from tools.environment import (analyze_repo_structure, check_git_config,
                               detect_repo_language_and_tools,
                               list_repo_config_files, read_build_gradle,
                               read_cargo_toml, read_docker_compose,
                               read_dockerfile, read_env_files, read_go_mod,
                               read_package_json, read_pom_xml,
                               read_pyproject_toml, read_requirements_txt)

# ============================================================================
# STRUCTURED OUTPUT MODEL
# ============================================================================


class EnvironmentAnalysis(BaseModel):
    """Structured output for environment analysis."""

    summary: str = Field(
        description="2-3 sentence executive summary of the project and its technology stack"
    )

    primary_languages: list[str] = Field(
        default_factory=list,
        description="Primary programming languages detected (e.g., ['Python', 'JavaScript'])",
    )

    project_type: str = Field(
        default="unknown",
        description="Type of project: web_app, library, cli_tool, microservices, monorepo, etc.",
    )

    frameworks: list[str] = Field(
        default_factory=list,
        description="Major frameworks detected (e.g., ['Django', 'React', 'Spring Boot'])",
    )

    package_managers: list[str] = Field(
        default_factory=list,
        description="Package managers in use (e.g., ['npm', 'pip', 'maven'])",
    )

    build_systems: list[str] = Field(
        default_factory=list,
        description="Build systems detected (e.g., ['webpack', 'gradle', 'make'])",
    )

    key_dependencies: list[str] = Field(
        default_factory=list,
        description="Top 10-15 most important production dependencies",
    )

    dev_tools: list[str] = Field(
        default_factory=list,
        description="Development tools: testing frameworks, linters, formatters (e.g., ['pytest', 'eslint', 'black'])",
    )

    containerization: Optional[dict] = Field(
        default=None,
        description="Docker/container info: {'has_dockerfile': bool, 'base_image': str, 'compose': bool}",
    )

    ci_cd: list[str] = Field(
        default_factory=list,
        description="CI/CD platforms detected (e.g., ['GitHub Actions', 'Jenkins'])",
    )

    environment_config: dict = Field(
        default_factory=dict,
        description="Environment configuration patterns: {'has_env_files': bool, 'multi_env': bool, 'key_vars': [...]}",
    )

    monorepo_structure: Optional[dict] = Field(
        default=None,
        description="If monorepo: {'workspaces': [...], 'structure': '...'}",
    )

    notable_features: list[str] = Field(
        default_factory=list,
        description="Special features or interesting aspects of the setup",
    )


# ============================================================================
# ENVIRONMENT SUMMARIZER AGENT
# ============================================================================


class EnvironmentSummarizerAgent(BaseAgent):
   """
   Agent for analyzing repository environment and configuration.

   This agent systematically analyzes a repository's structure and configuration
   files to provide a comprehensive understanding of:
   - Project technology stack
   - Dependencies and their versions
   - Build and deployment infrastructure
   - Environment configuration requirements
   - Development tooling and CI/CD setup

   Attributes:
      prompt: System prompt guiding the agent's analysis
      tools: Tools available for repository analysis
      return_state_field: LangGraph state field name
      response_format: Pydantic model for structured output
      temperature: LLM temperature (0.3 for deterministic analysis)
      max_iterations: Maximum agentic loop iterations (6)
   """

   prompt = """You are an expert repository environment analyzer. Analyze the code repository to provide a comprehensive summary of its technology stack, dependencies, and configuration.

## Analysis Steps

1. Start by detecting the repository language and available tools
2. Gather common repository information:
   - Configuration files and structure
   - Git setup and repository metadata
   - Docker/containerization setup
   - Environment configuration
3. Based on detected language(s), analyze language-specific metadata:
   - JavaScript/Node.js: package.json
   - Python: pyproject.toml, requirements.txt
   - Java: pom.xml, build.gradle
   - Go: go.mod
   - Rust: Cargo.toml
4. Synthesize all information into structured output

## Return your analysis with:
- summary: 2-3 sentence overview of the project and its tech stack
- primary_languages: Main programming languages detected
- project_type: web_app, library, cli_tool, microservices, monorepo, etc.
- frameworks: Major frameworks and libraries
- package_managers: Package managers in use
- build_systems: Build tools detected
- key_dependencies: Top 10-15 important production dependencies
- dev_tools: Testing, linting, formatting tools
- containerization: Docker/container configuration (if present)
- ci_cd: CI/CD platforms detected
- environment_config: Environment variable patterns
- monorepo_structure: Monorepo workspace info (if applicable)
- notable_features: Interesting or important setup aspects

## Guidelines
- Be thorough but concise
- Focus on actionable insights
- Prioritize core dependencies over dev dependencies
- If a config file has errors, note it but continue analysis"""

    #  temperature = 0.15
    # max_iterations = 10
   structured_output_type = EnvironmentAnalysis
   return_state_field = "environment_analysis"

   tools = [
      # ALWAYS USE FIRST: Language detection
      detect_repo_language_and_tools,
      # Common analysis tools (use on all repos)
      list_repo_config_files,
      analyze_repo_structure,
      check_git_config,
      # Containerization & environment (use when detected)
      read_dockerfile,
      read_docker_compose,
      read_env_files,
      # Language-specific tools (use based on detect_repo_language_and_tools results)
      read_package_json,  # JavaScript/Node.js
      read_requirements_txt,  # Python
      read_pyproject_toml,  # Python (modern)
      read_pom_xml,  # Java (Maven)
      read_build_gradle,  # Java (Gradle)
      read_go_mod,  # Go
      read_cargo_toml,  # Rust
   ]
