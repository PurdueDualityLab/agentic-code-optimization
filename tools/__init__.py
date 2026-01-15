"""Tools for agents."""

from tools.behavior import (
    analyze_code_complexity,
    analyze_code_structure,
    analyze_data_dependencies,
    analyze_error_handling_strategy,
    analyze_functions,
    analyze_function_interactions,
    detect_performance_bottlenecks,
    extract_code_documentation,
    identify_code_patterns,
)
from tools.component import (
    analyze_classes,
    analyze_component_boundaries,
    analyze_inheritance_hierarchy,
    analyze_module_structure,
    analyze_public_apis,
    analyze_service_architecture,
)
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
from tools.analysis import (
    build_analysis_bundle,
    load_environment_summary,
    load_static_analysis,
    read_code_snippet,
)

__all__ = [
    # Environment tools
    "list_repo_config_files",
    "analyze_repo_structure",
    "check_git_config",
    "read_package_json",
    "read_requirements_txt",
    "read_pyproject_toml",
    "read_dockerfile",
    "read_docker_compose",
    "read_env_files",
    "read_pom_xml",
    "read_build_gradle",
    "read_go_mod",
    "read_cargo_toml",
    # Behavior tools
    "analyze_functions",
    "analyze_code_structure",
    "analyze_function_interactions",
    "identify_code_patterns",
    "analyze_error_handling_strategy",
    "analyze_data_dependencies",
    "detect_performance_bottlenecks",
    "extract_code_documentation",
    "analyze_code_complexity",
    # Component tools
    "analyze_classes",
    "analyze_module_structure",
    "analyze_public_apis",
    "analyze_component_boundaries",
    "analyze_inheritance_hierarchy",
    "analyze_service_architecture",
    # Analysis tools
    "load_environment_summary",
    "load_static_analysis",
    "build_analysis_bundle",
    "read_code_snippet",
]
