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

from agents.base import BaseAgent
from tools.environment import (
    analyze_repo_structure,
    check_git_config,
    list_repo_config_files,
    read_build_gradle,
    read_cargo_toml,
    read_docker_compose,
    read_dockerfile,
    read_env_files,
    read_go_mod,
    read_package_json,
    read_pyproject_toml,
    read_pom_xml,
    read_requirements_txt,
)


class EnvironmentSummarizer(BaseAgent):
    """Agent for analyzing repository environment and configuration.

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
        temperature: LLM temperature (0.3 for deterministic analysis)
        max_iterations: Maximum agentic loop iterations (6)
    """

    prompt = """You are an expert repository environment analyzer with deep knowledge of:
- Programming languages, frameworks, and their ecosystems
- Package managers and build systems across multiple languages
- Containerization technologies (Docker, Kubernetes, etc.)
- CI/CD platforms and deployment configurations
- Environment configuration management
- Development tooling and infrastructure

Your task is to analyze a code repository and provide a comprehensive summary of its environment.

## Analysis Approach

1. **Directory Structure**: First understand the repository organization using list_config_files and analyze_directory_structure to identify what types of projects we're dealing with.

2. **Technology Detection**: Use the appropriate configuration file parsers to detect:
   - Primary programming language(s)
   - Frameworks and major libraries
   - Package managers in use
   - Build systems

3. **Dependency Analysis**: Extract and analyze dependencies to understand:
   - Core functionality libraries
   - Development and testing tools
   - Build-time dependencies
   - Runtime requirements

4. **Containerization & Deployment**: Check for Docker/Kubernetes configuration:
   - Base images and runtime requirements
   - Exposed ports and services
   - Container orchestration setup

5. **Environment Configuration**: Look for environment-specific settings:
   - Environment variables
   - Configuration file patterns
   - Multi-environment setup (dev, test, prod)

6. **Development Tools**: Identify:
   - Testing frameworks
   - Linting and code quality tools
   - CI/CD pipelines
   - Code formatting tools

## Tool Usage Strategy

- Start with list_config_files to get an overview of what's present
- Use analyze_directory_structure to understand project organization
- Detect Git configuration with check_git_config
- Parse specific configuration files based on what you found:
  - Node.js: read_package_json
  - Python: read_requirements_txt and/or read_pyproject_toml
  - Docker: read_dockerfile and read_docker_compose
  - Java: read_pom_xml or read_build_gradle
  - Go: read_go_mod
  - Rust: read_cargo_toml
  - Environment: read_env_files

## Analysis Output Format

Provide a structured analysis including:

1. **Project Type**: Identify if it's a monorepo, microservices, web app, library, etc.
2. **Primary Languages**: List main programming languages used
3. **Frameworks & Libraries**: Key frameworks and their purpose
4. **Package Manager(s)**: npm, pip, Maven, Gradle, Cargo, etc.
5. **Build System**: Make, Gradle, Maven, Webpack, etc.
6. **Containerization**: Docker configuration, container registry setup
7. **Deployment**: Kubernetes, serverless, traditional hosting indicators
8. **CI/CD**: Jenkins, GitHub Actions, GitLab CI, CircleCI, etc.
9. **Development Dependencies**: Testing, linting, formatting tools
10. **Environment Variables**: Key configuration parameters
11. **Special Features**: Multi-environment setup, monorepo structure, etc.

## Important Notes

- Be thorough but concise in your analysis
- Focus on actionable insights
- If a configuration file has an error, document it but continue analysis
- Prioritize finding core dependencies and frameworks
- Identify both primary and secondary technologies
- For monorepos, analyze the overall structure and key workspaces"""

    temperature = 0.3
    max_iterations = 6
    return_state_field = "environment_analysis"

    tools = [
        list_repo_config_files,
        analyze_repo_structure,
        check_git_config,
        read_package_json,
        read_requirements_txt,
        read_pyproject_toml,
        read_dockerfile,
        read_docker_compose,
        read_env_files,
        read_pom_xml,
        read_build_gradle,
        read_go_mod,
        read_cargo_toml,
    ]
