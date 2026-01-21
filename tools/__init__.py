"""Tools for agents."""

from .analysis import (build_analysis_bundle, read_code_snippet, read_file,
                       search_codebase)
from .benchmark import run_benchmark_command, run_benchmark_comparison
from .behavior import (analyze_code_complexity, analyze_code_structure,
                       analyze_data_dependencies,
                       analyze_error_handling_strategy,
                       analyze_function_interactions, analyze_functions,
                       detect_performance_bottlenecks,
                       extract_code_documentation, identify_code_patterns)
from .common import (  # File operations; Parsing; Writing; Utilities; Response helpers
    check_file_exists, count_files_with_extension, create_error_response,
    create_not_found_response, create_success_response,
    ensure_directory_exists, get_file_size, list_files_in_directory,
    parse_json_file, parse_json_string, parse_toml_file, parse_xml_file,
    parse_xml_string, parse_yaml_file, parse_yaml_string, read_file,
    read_file_bytes, write_file, write_file_bytes, write_json_file,
    write_yaml_file)
from .component import (analyze_classes, analyze_component_boundaries,
                        analyze_inheritance_hierarchy,
                        analyze_module_structure, analyze_public_apis,
                        analyze_service_architecture)
from .environment import (analyze_repo_structure, check_git_config,
                          detect_repo_language_and_tools,
                          list_repo_config_files, read_build_gradle,
                          read_cargo_toml, read_go_mod,
                          read_package_json, read_pom_xml, read_pyproject_toml,
                          read_requirements_txt)
from .optimizer import (apply_snippet_patch, apply_snippet_patch_guarded,
                        load_analysis_report, load_summary_text,
                        preview_snippet_patch, preview_snippet_patch_guarded)
