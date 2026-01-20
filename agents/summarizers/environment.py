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
                               read_cargo_toml, read_go_mod,
                               read_package_json, read_pom_xml,
                               read_pyproject_toml, read_requirements_txt)

# ============================================================================
# STRUCTURED OUTPUT MODEL
# ============================================================================


class EnvironmentAnalysis(BaseModel):
    """Structured output for environment analysis focused on architectural characteristics."""

    summary: str = Field(
        description="2-3 sentence executive summary of the project's computational characteristics and architecture"
    )

    primary_languages: list[str] = Field(
        default_factory=list,
        description="Primary programming languages detected (e.g., ['Python', 'C++', 'CUDA'])",
    )

    project_type: str = Field(
        default="unknown",
        description="Type of project: scientific_computing, hpc, ml_framework, signal_processing, graphics, general_compute, etc.",
    )

    frameworks: list[str] = Field(
        default_factory=list,
        description="Computational frameworks detected (e.g., ['NumPy', 'CUDA', 'OpenMP', 'MPI', 'TensorFlow'])",
    )

    target_architectures: list[str] = Field(
        default_factory=list,
        description="Target hardware architectures mentioned or inferred (e.g., ['x86-64', 'ARM', 'GPU', 'SIMD-capable systems'])",
    )

    cpu_profile: dict = Field(
        default_factory=dict,
        description="CPU characteristics from code analysis: {'vectorization': bool, 'simd_level': 'SSE/AVX/AVX-512', 'parallelization': 'OpenMP/pthreads/etc.', 'cache_aware': bool}",
    )

    memory_profile: dict = Field(
        default_factory=dict,
        description="Memory characteristics: {'access_pattern': 'sequential/random/strided', 'bandwidth_sensitive': bool, 'memory_intensive': bool, 'working_set_estimate': str}",
    )

    parallelization_model: str = Field(
        default="unknown",
        description="Parallelization approach: data_parallel, task_parallel, shared_memory, distributed, gpu_accelerated, hybrid, or unknown",
    )

    simd_capabilities: str = Field(
        default="",
        description="SIMD/vectorization capabilities detected: scalar, sse, avx, avx2, avx-512, neon, wasm-simd, or unknown",
    )

    data_characteristics: dict = Field(
        default_factory=dict,
        description="Data parallelism patterns: {'data_parallel': bool, 'fine_grained': bool, 'stencil_operations': bool, 'irregular_access': bool}",
    )

    performance_optimization_targets: list[str] = Field(
        default_factory=list,
        description="Performance characteristics the code targets (e.g., ['throughput', 'latency', 'memory_bandwidth', 'cache_efficiency'])",
    )

    computational_characteristics: dict = Field(
        default_factory=dict,
        description="Computational properties: {'compute_intensive': bool, 'io_intensive': bool, 'communication_intensive': bool, 'synchronization_heavy': bool}",
    )

    notable_features: list[str] = Field(
        default_factory=list,
        description="Special architectural or performance-related aspects (e.g., ['custom SIMD kernels', 'GPU offloading', 'cache-oblivious algorithms'])",
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

   prompt = """You are an expert computational architect analyzing a repository to understand its hardware and performance characteristics.

Analyze the codebase to determine:
1. What computational problems does this code solve?
2. What hardware architectures is it targeting or optimized for?
3. What parallelization strategies does it use?
4. What are the memory and compute patterns?
5. What performance optimization approaches are evident?

## Analysis Focus Areas

- **Programming Languages**: Computational languages used (C++, CUDA, SIMD, etc.)
- **Computational Frameworks**: Libraries for HPC, ML, signal processing, graphics, etc.
- **Target Architectures**: x86, ARM, GPU, FPGA, or specialized hardware mentioned in code
- **Parallelization**: OpenMP, MPI, GPU acceleration, threading models, SIMD vectorization
- **Memory Patterns**: Sequential access, strided, random, memory bandwidth requirements
- **Data Characteristics**: Data-parallel vs task-parallel, fine-grained vs coarse-grained
- **Performance Targets**: Throughput, latency, memory efficiency, cache optimization
- **Computational Properties**: Compute-intensive, I/O-intensive, communication-heavy
- **Optimization Techniques**: Vectorization, loop tiling, cache-aware algorithms, kernel fusion

## Return Structured Analysis:
- summary: 2-3 sentences on computational characteristics and target hardware
- primary_languages: Languages used (C++, CUDA, Fortran, Python, etc.)
- project_type: scientific_computing, hpc, ml_framework, signal_processing, graphics, general_compute
- frameworks: Computational frameworks (NumPy, CUDA, OpenMP, MPI, TensorFlow, etc.)
- target_architectures: Hardware targets (x86-64, ARM, GPU, specialized hardware)
- cpu_profile: SIMD levels (SSE/AVX/AVX-512), parallelization methods, cache awareness
- memory_profile: Access patterns, bandwidth sensitivity, memory intensity, working set size
- parallelization_model: data_parallel, task_parallel, shared_memory, distributed, gpu_accelerated, hybrid
- simd_capabilities: SIMD support level detected
- data_characteristics: Fine-grained parallelism, stencil patterns, irregular access
- performance_optimization_targets: What performance metrics matter (throughput, latency, etc.)
- computational_characteristics: Compute vs I/O vs communication intensity
- notable_features: Performance-critical algorithms, custom kernels, GPU offloading, etc.

## Guidelines
- Focus on computational and architectural aspects, not build/deployment infrastructure
- Look for evidence in code comments, macro names, compiler flags, library usage
- Infer from algorithms: loops with parallelization pragmas, vectorization patterns, GPU kernels
- Consider memory layout and access patterns from code structure
- Identify performance-critical bottlenecks"""

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
      # Language-specific tools (use based on detect_repo_language_and_tools results)
      read_package_json,  # JavaScript/Node.js
      read_requirements_txt,  # Python
      read_pyproject_toml,  # Python (modern)
      read_pom_xml,  # Java (Maven)
      read_build_gradle,  # Java (Gradle)
      read_go_mod,  # Go
      read_cargo_toml,  # Rust
   ]
