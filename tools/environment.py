"""Tools for EnvironmentSummarizer agent - all code self-contained."""

from __future__ import annotations

# ============================================================================
# IMPORTS
# ============================================================================

# Standard library
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Annotated, Any

# LangChain
from langchain_core.tools import tool

# Local imports
from tools.common import (
    check_file_exists,
    parse_json_file,
    parse_toml_file,
    parse_yaml_file,
    parse_xml_file,
    create_error_response,
    create_not_found_response,
    count_files_with_extension,
)

# ============================================================================
# LOGGER SETUP
# ============================================================================

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# Language detection indicators - mapping file patterns/extensions to languages
LANGUAGE_INDICATORS = {
    "javascript": {
        "files": ["package.json", "package-lock.json", "tsconfig.json", "yarn.lock", "pnpm-lock.yaml"],
        "extensions": [".js", ".jsx", ".ts", ".tsx", ".mjs"],
        "directories": ["node_modules"],
    },
    "python": {
        "files": ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile", "poetry.lock"],
        "extensions": [".py", ".pyw"],
        "directories": ["__pycache__", "venv", ".venv"],
    },
    "java": {
        "files": ["pom.xml", "build.gradle", "build.gradle.kts", "gradle.properties"],
        "extensions": [".java", ".class", ".jar"],
        "directories": ["src/main/java", "target", "build"],
    },
    "go": {
        "files": ["go.mod", "go.sum"],
        "extensions": [".go"],
        "directories": ["vendor"],
    },
    "rust": {
        "files": ["Cargo.toml", "Cargo.lock"],
        "extensions": [".rs"],
        "directories": ["target"],
    },
    "c_cpp": {
        "files": ["CMakeLists.txt", "Makefile"],
        "extensions": [".c", ".cpp", ".cc", ".h", ".hpp"],
        "directories": ["build", "cmake"],
    },
    "ruby": {
        "files": ["Gemfile", "Gemfile.lock", "Rakefile"],
        "extensions": [".rb"],
        "directories": ["vendor/bundle"],
    },
    "php": {
        "files": ["composer.json", "composer.lock"],
        "extensions": [".php"],
        "directories": ["vendor"],
    },
}

# Configuration file patterns organized by category
CONFIG_PATTERNS = {
    "build_system": ["Makefile", "CMakeLists.txt", "build.sh", "setup.py", "setup.cfg", "Rakefile", "Gemfile"],
    "package_managers": ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "requirements.txt",
                       "Pipfile", "Pipfile.lock", "pyproject.toml", "poetry.lock", "Gemfile.lock", "composer.json",
                       "composer.lock", "go.mod", "go.sum", "Cargo.toml", "Cargo.lock", "pom.xml", "build.gradle",
                       "build.gradle.kts", "gradle.properties"],
    "containerization": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "Dockerfile.dev",
                       "Dockerfile.prod", ".dockerignore", "kubernetes.yml", "k8s.yml", "helm.yaml", "Chart.yaml"],
    "ci_cd": [".github", ".gitlab-ci.yml", ".gitignore", "azure-pipelines.yml", ".circleci", "Jenkinsfile",
             ".travis.yml", "tox.ini", ".flake8", "codecov.yml"],
    "environment": [".env", ".env.example", ".env.local", ".env.test", ".env.production", ".env.development",
                   ".envrc", ".nix", "nix.flake"],
    "web_frameworks": ["nuxt.config.ts", "nuxt.config.js", "next.config.js", "vercel.json", "astro.config.mjs",
                      "vite.config.ts", "vite.config.js", "webpack.config.js", "rollup.config.js", "gatsby-config.js"],
    "documentation": ["README.md", "CONTRIBUTING.md", "docs", "LICENSE", "AUTHORS", "CHANGELOG.md"],
    "code_quality": [".eslintrc.js", ".eslintrc.json", ".prettierrc", ".prettierignore", "tsconfig.json",
                    ".editorconfig", "jest.config.js", "vitest.config.ts", "pylintrc", "mypy.ini",
                    ".pre-commit-config.yaml"],
}

# Mapping from detected languages to recommended tools
LANGUAGE_TOOL_MAPPING = {
    "javascript": ["read_package_json"],
    "python": ["read_requirements_txt", "read_pyproject_toml"],
    "java": ["read_pom_xml", "read_build_gradle"],
    "go": ["read_go_mod"],
    "rust": ["read_cargo_toml"],
}

# Common tools that should always be recommended
COMMON_TOOLS = [
    "list_repo_config_files",
    "analyze_repo_structure",
    "check_git_config",
    "read_dockerfile",
    "read_docker_compose",
    "read_env_files",
]

# Note: Helper functions moved to tools/common.py for reusability


# ============================================================================
# LANGUAGE DETECTION
# ============================================================================


@tool
def detect_repo_language_and_tools(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """Detect repository programming language(s) and recommend analysis tools.

    Analyzes the repository to identify the primary and secondary programming
    languages based on file patterns, extensions, and directory structure.
    Returns a list of recommended tools to run for comprehensive analysis.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - primary_language: str - Most likely primary language
        - detected_languages: list - All detected languages
        - confidence: str - Detection confidence (high/medium/low)
        - recommended_tools: list - Tools to run for this repository
        - detection_signals: dict - Evidence for each detected language

    Example:
        >>> result = detect_repo_language_and_tools("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["primary_language"]
        "python"
        >>> data["recommended_tools"]
        ["list_repo_config_files", "read_pyproject_toml", ...]
    """
    try:
        root_path = Path(repo_path)
        if not root_path.exists():
            return create_error_response("Repository path does not exist", repo_path, found=False)

        # Track detection signals for each language
        language_scores: dict[str, dict[str, Any]] = {}

        for language, indicators in LANGUAGE_INDICATORS.items():
            score = 0
            signals = []

            # Check for indicator files (high weight)
            for file_pattern in indicators.get("files", []):
                if (root_path / file_pattern).exists():
                    score += 10
                    signals.append(file_pattern)

            # Check for indicator directories (medium weight)
            for dir_pattern in indicators.get("directories", []):
                if (root_path / dir_pattern).exists():
                    score += 5
                    signals.append(f"{dir_pattern}/")

            # Check for files with specific extensions (variable weight based on count)
            for ext in indicators.get("extensions", []):
                file_count = count_files_with_extension(root_path, ext, max_depth=3)
                if file_count > 0:
                    score += min(file_count, 20)  # Cap at 20 points
                    signals.append(f"{file_count} *{ext} files")

            if score > 0:
                language_scores[language] = {"score": score, "signals": signals}

        # Sort languages by score
        sorted_languages = sorted(language_scores.items(), key=lambda x: x[1]["score"], reverse=True)

        if not sorted_languages:
            # No language detected, recommend only common tools
            return json.dumps({
                "primary_language": "unknown",
                "detected_languages": [],
                "confidence": "none",
                "recommended_tools": COMMON_TOOLS,
                "detection_signals": {},
            }, indent=2)

        # Primary language is the highest scored
        primary_language = sorted_languages[0][0]
        primary_score = sorted_languages[0][1]["score"]

        # Include languages with score > 10% of primary
        threshold = primary_score * 0.1
        detected_languages = [lang for lang, data in sorted_languages if data["score"] >= threshold]

        # Determine confidence based on primary score and gap to second
        if primary_score >= 30:
            confidence = "high"
        elif primary_score >= 15:
            confidence = "medium"
        else:
            confidence = "low"

        # Build recommended tools list
        recommended_tools = list(COMMON_TOOLS)  # Start with common tools

        # Add language-specific tools
        for language in detected_languages:
            if language in LANGUAGE_TOOL_MAPPING:
                for tool in LANGUAGE_TOOL_MAPPING[language]:
                    if tool not in recommended_tools:
                        recommended_tools.append(tool)

        # Format detection signals for output
        detection_signals = {lang: data["signals"] for lang, data in language_scores.items()}

        return json.dumps({
            "primary_language": primary_language,
            "detected_languages": detected_languages,
            "confidence": confidence,
            "recommended_tools": recommended_tools,
            "detection_signals": detection_signals,
        }, indent=2)

    except Exception as e:
        logger.error(f"Error detecting repository language: {str(e)}")
        return create_error_response(f"Failed to detect language: {str(e)}", repo_path)


# ============================================================================
# COMMON TOOLS
# ============================================================================
# These tools work across all repository types and programming languages


@tool
async def list_repo_config_files(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """List all configuration files found in repository root.

    Scans the repository root directory for common configuration files
    across different categories: build systems, package managers, CI/CD,
    containerization, environment files, web frameworks, documentation,
    and code quality tools.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - found: bool - Whether any config files were found
        - total_config_files: int - Total count of config files
        - config_files_by_category: dict - Config files grouped by category

    Example:
        >>> result = await list_repo_config_files("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["total_config_files"]
        15
    """
    found_configs = {category: [] for category in CONFIG_PATTERNS}
    root_path = Path(repo_path)

    # Scan for each config file pattern
    for category, patterns in CONFIG_PATTERNS.items():
        for pattern in patterns:
            if (root_path / pattern).exists():
                found_configs[category].append(pattern)

    total_found = sum(len(items) for items in found_configs.values())
    result = {
        "found": total_found > 0,
        "total_config_files": total_found,
        "config_files_by_category": found_configs
    }
    return json.dumps(result, indent=2)


@tool
def analyze_repo_structure(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """Analyze repository directory structure to identify project type and organization.

    Examines the top-level directory structure, file extensions, and common
    project patterns (test directories, documentation, examples, etc.) to
    understand the repository organization. Also detects monorepo indicators.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - found: bool - Whether analysis succeeded
        - path: str - Repository path
        - top_level_directories: list - Names of top-level directories
        - file_extensions_at_root: dict - File extensions and counts at root
        - project_markers: dict - Detected project patterns
        - monorepo_indicators: dict - Monorepo detection results
        - subdirectories: dict - File counts for top subdirectories
        - error: str - Error message (if analysis failed)

    Example:
        >>> result = analyze_repo_structure("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["top_level_directories"]
        ["src", "tests", "docs"]
    """
    try:
        root_path = Path(repo_path)
        analysis = {"found": True, "path": str(root_path), "max_depth": 3}

        # Get top-level directories
        top_dirs = [item.name for item in root_path.iterdir() if item.is_dir() and not item.name.startswith(".")]
        analysis["top_level_directories"] = sorted(top_dirs)

        # Identify project structure markers
        project_markers = {}
        for pattern in ["src", "lib", "source", "code"]:
            if pattern in top_dirs:
                project_markers[f"has_{pattern}_dir"] = True

        # Identify test directories
        test_patterns = ["test", "tests", "spec", "specs", "__tests__"]
        test_dirs = [d for d in top_dirs if any(p in d for p in test_patterns)]
        project_markers["test_directories"] = test_dirs

        # Identify documentation directories
        doc_patterns = ["doc", "docs", "documentation", "wiki"]
        doc_dirs = [d for d in top_dirs if any(p in d for p in doc_patterns)]
        project_markers["documentation_directories"] = doc_dirs

        # Identify example directories
        example_patterns = ["example", "examples", "sample", "samples"]
        example_dirs = [d for d in top_dirs if any(p in d for p in example_patterns)]
        project_markers["example_directories"] = example_dirs

        # Count file extensions at root level
        file_extensions = {}
        for item in root_path.iterdir():
            if item.is_file():
                ext = item.suffix or "no_extension"
                file_extensions[ext] = file_extensions.get(ext, 0) + 1

        analysis["file_extensions_at_root"] = file_extensions
        analysis["project_markers"] = project_markers

        # Detect monorepo indicators
        monorepo_indicators = {
            "workspaces": (root_path / "package.json").exists(),
            "lerna": (root_path / "lerna.json").exists(),
            "yarn_workspaces": any((root_path / d).exists() for d in ["packages", "apps"]),
        }
        analysis["monorepo_indicators"] = monorepo_indicators

        # Analyze subdirectories (limit to top 10 for performance)
        subdirs_analysis = {}
        for directory in sorted(top_dirs)[:10]:
            dir_path = root_path / directory
            try:
                file_count = sum(1 for _ in dir_path.rglob("*") if _.is_file())
                subdirs_analysis[directory] = {"file_count": min(file_count, 1000)}
            except Exception as e:
                logger.debug(f"Error analyzing subdirectory {directory}: {str(e)}")

        analysis["subdirectories"] = subdirs_analysis
        return json.dumps(analysis, indent=2)

    except Exception as e:
        logger.error(f"Error analyzing directory structure: {str(e)}")
        return create_error_response(f"Failed to analyze: {str(e)}", repo_path)


@tool
def check_git_config(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """Detect and analyze Git configuration and repository metadata.

    Checks for the presence of a Git repository and analyzes its configuration,
    including remote URLs, hooks, and standard Git directory structure.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - found: bool - Whether a Git repository was detected
        - path: str - Path to .git directory (if found)
        - is_bare: bool - Whether it's a bare repository
        - has_config: bool - Whether Git config exists
        - remote_url: str - Remote repository URL (if configured)
        - has_hooks: bool - Whether hooks directory exists
        - has_objects: bool - Whether objects directory exists
        - has_refs: bool - Whether refs directory exists
        - has_gitignore: bool - Whether .gitignore exists
        - message: str - Status message (if not found)
        - error: str - Error message (if analysis failed)

    Example:
        >>> result = check_git_config("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["found"]
        True
        >>> data["remote_url"]
        "https://github.com/user/repo.git"
    """
    git_dir = Path(repo_path) / ".git"
    if not git_dir.exists():
        return json.dumps({"found": False, "message": "Git repository not detected"}, indent=2)

    try:
        analysis = {"found": True, "path": str(git_dir)}

        # Check if bare repository
        if (git_dir / "bare").exists():
            analysis["is_bare"] = True

        # Parse Git config for remote URL
        config_path = git_dir / "config"
        if config_path.exists():
            content = config_path.read_text()
            analysis["has_config"] = True
            # Extract remote URL
            for line in content.split("\n"):
                if "url = " in line:
                    analysis["remote_url"] = line.split("url = ")[1].strip()
                    break

        # Check for standard Git directories
        analysis["has_hooks"] = (git_dir / "hooks").exists()
        analysis["has_objects"] = (git_dir / "objects").exists()
        analysis["has_refs"] = (git_dir / "refs").exists()
        analysis["has_gitignore"] = (Path(repo_path) / ".gitignore").exists()

        return json.dumps(analysis, indent=2)

    except Exception as e:
        logger.error(f"Error analyzing Git config: {str(e)}")
        return create_error_response(f"Failed to analyze: {str(e)}", str(git_dir))


@tool
def read_dockerfile(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """Parse Dockerfile for container configuration details.

    Analyzes a Dockerfile to extract key information including base image,
    exposed ports, environment variables, and overall structure.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - found: bool - Whether Dockerfile was found
        - path: str - Path to Dockerfile (if found)
        - base_image: str - Base image from FROM instruction
        - exposed_ports: list - Ports exposed via EXPOSE instruction
        - environment_variables: dict - Environment variables from ENV instructions
        - raw_content: str - First 500 characters of Dockerfile
        - total_lines: int - Total line count
        - message: str - Status message (if not found)
        - error: str - Error message (if parsing failed)

    Example:
        >>> result = read_dockerfile("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["base_image"]
        "python:3.11-slim"
    """
    # Check if Dockerfile exists
    exists, dockerfile_path = check_file_exists(repo_path, "Dockerfile")
    if not exists:
        return create_not_found_response("Dockerfile")

    try:
        content = dockerfile_path.read_text()
        analysis = {"found": True, "path": str(dockerfile_path)}

        # Extract base image (FROM instruction)
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("FROM "):
                analysis["base_image"] = line[5:].split()[0]
                break

        # Extract exposed ports
        exposed_ports = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("EXPOSE "):
                exposed_ports.extend(line[7:].split())
        analysis["exposed_ports"] = exposed_ports

        # Extract environment variables
        env_vars = {}
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("ENV "):
                env_part = line[4:]
                if "=" in env_part:
                    key, value = env_part.split("=", 1)
                    env_vars[key.strip()] = value.strip()
        analysis["environment_variables"] = env_vars

        # Include partial content and metadata
        analysis["raw_content"] = content[:500]
        analysis["total_lines"] = len(content.split("\n"))

        return json.dumps(analysis, indent=2)

    except Exception as e:
        logger.error(f"Error parsing Dockerfile: {str(e)}")
        return create_error_response(f"Failed to parse: {str(e)}", str(dockerfile_path))


@tool
def read_docker_compose(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """Parse docker-compose.yml for multi-container application setup.

    Analyzes Docker Compose configuration to extract service definitions,
    environment variables, and volume configurations.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - found: bool - Whether docker-compose file was found
        - path: str - Path to docker-compose file (if found)
        - version: str - Docker Compose version
        - services: list - List of service names
        - environment_variables: dict - Environment variables across services
        - volumes: dict - Volume definitions
        - message: str - Status message (if not found)
        - error: str - Error message (if parsing failed)

    Example:
        >>> result = read_docker_compose("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["services"]
        ["web", "db", "redis"]
    """
    # Check multiple possible docker-compose file names
    compose_files = ["docker-compose.yml", "docker-compose.yaml", "compose.yml"]

    for filename in compose_files:
        exists, compose_path = check_file_exists(repo_path, filename)
        if exists:
            # Parse YAML file
            data = parse_yaml_file(compose_path)
            if data is None:
                return create_error_response("Failed to parse YAML file", str(compose_path))

            if not isinstance(data, dict):
                return create_error_response("Invalid docker-compose format", str(compose_path))

            try:
                analysis = {
                    "found": True,
                    "path": str(compose_path),
                    "version": data.get("version", "unknown")
                }

                # Extract service names
                services = data.get("services", {})
                analysis["services"] = list(services.keys()) if isinstance(services, dict) else []

                # Extract environment variables from all services
                env_vars = {}
                if isinstance(services, dict):
                    for service_name, service_config in services.items():
                        if isinstance(service_config, dict) and "environment" in service_config:
                            env = service_config.get("environment", {})
                            # Handle both dict and list formats
                            if isinstance(env, dict):
                                env_vars.update(env)
                            elif isinstance(env, list):
                                for item in env:
                                    if "=" in item:
                                        k, v = item.split("=", 1)
                                        env_vars[k] = v

                analysis["environment_variables"] = env_vars
                analysis["volumes"] = data.get("volumes", {})

                return json.dumps(analysis, indent=2)

            except Exception as e:
                logger.error(f"Error parsing {compose_path}: {str(e)}")
                return create_error_response(f"Failed to parse: {str(e)}", str(compose_path))

    # No docker-compose file found
    return create_not_found_response("docker-compose files")


@tool
def read_env_files(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """Parse .env files for environment variable configuration.

    Scans for common .env file variants and extracts environment variable
    definitions. Useful for understanding configuration requirements.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - found: bool - Whether any .env files were found
        - files: list - Paths to found .env files
        - variables: dict - Merged environment variables from all files
        - message: str - Status message (if not found)

    Example:
        >>> result = read_env_files("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["variables"]
        {"DATABASE_URL": "...", "API_KEY": "..."}
    """
    env_file_names = [".env", ".env.local", ".env.example"]
    all_vars = {}
    found_files = []

    # Check each possible .env file
    for filename in env_file_names:
        exists, env_file = check_file_exists(repo_path, filename)
        if exists:
            try:
                content = env_file.read_text()
                found_files.append(str(env_file))

                # Parse environment variables
                for line in content.split("\n"):
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue
                    # Parse KEY=VALUE format
                    if "=" in line:
                        key, value = line.split("=", 1)
                        all_vars[key.strip()] = value.strip()

            except Exception as e:
                logger.error(f"Error parsing {env_file}: {str(e)}")

    # Return results
    if found_files:
        return json.dumps({
            "found": True,
            "files": found_files,
            "variables": all_vars
        }, indent=2)
    else:
        return create_not_found_response(".env files")


# ============================================================================
# LANGUAGE-SPECIFIC TOOLS: JAVASCRIPT/NODE.JS
# ============================================================================


@tool
def read_package_json(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """Parse package.json for Node.js/JavaScript project configuration.

    Extracts package metadata, dependencies, scripts, and engine requirements
    from a package.json file.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - found: bool - Whether package.json was found
        - path: str - Path to package.json (if found)
        - name: str - Package name
        - version: str - Package version
        - description: str - Package description
        - type: str - Module type (commonjs/module)
        - dependencies: list - Production dependency names
        - dev_dependencies: list - Development dependency names
        - peer_dependencies: list - Peer dependency names
        - scripts: list - Available npm script names
        - engines: dict - Node/npm version requirements
        - author: str - Package author
        - license: str - Package license
        - message: str - Status message (if not found)
        - error: str - Error message (if parsing failed)

    Example:
        >>> result = read_package_json("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["dependencies"]
        ["react", "express", "lodash"]
    """
    # Check if package.json exists
    exists, package_json_path = check_file_exists(repo_path, "package.json")
    if not exists:
        return create_not_found_response("package.json")

    # Parse JSON file
    data = parse_json_file(package_json_path)
    if data is None:
        return create_error_response("Invalid JSON", str(package_json_path))

    # Extract and return analysis
    analysis = {
        "found": True,
        "path": str(package_json_path),
        "name": data.get("name", ""),
        "version": data.get("version", ""),
        "description": data.get("description", ""),
        "type": data.get("type", "commonjs"),
        "dependencies": list(data.get("dependencies", {}).keys()),
        "dev_dependencies": list(data.get("devDependencies", {}).keys()),
        "peer_dependencies": list(data.get("peerDependencies", {}).keys()),
        "scripts": list(data.get("scripts", {}).keys()),
        "engines": data.get("engines", {}),
        "author": data.get("author", ""),
        "license": data.get("license", ""),
    }
    return json.dumps(analysis, indent=2)


# ============================================================================
# LANGUAGE-SPECIFIC TOOLS: PYTHON
# ============================================================================


@tool
def read_requirements_txt(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """Parse requirements.txt files for Python project dependencies.

    Scans for multiple requirements file variants (requirements.txt,
    requirements-dev.txt, requirements-prod.txt) and extracts Python
    package dependencies.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - found: bool - Whether any requirements files were found
        - files: dict - Package lists by requirements file
        - total_dependencies: int - Total unique dependency count
        - message: str - Status message (if not found)

    Example:
        >>> result = read_requirements_txt("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["files"]["requirements.txt"]
        ["django", "requests", "pytest"]
    """
    req_file_names = ["requirements.txt", "requirements-dev.txt", "requirements-prod.txt"]
    all_requirements = {}

    # Check each possible requirements file
    for filename in req_file_names:
        exists, req_file = check_file_exists(repo_path, filename)
        if exists:
            try:
                content = req_file.read_text()
                packages = []

                # Parse each line for package names
                for line in content.split("\n"):
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue
                    # Extract package name (before version specifiers)
                    pkg = re.split(r'[\[\>=<~!]', line)[0].strip()
                    if pkg:
                        packages.append(pkg)

                all_requirements[req_file.name] = packages

            except Exception as e:
                logger.error(f"Error parsing {req_file}: {str(e)}")

    # Return results
    if all_requirements:
        return json.dumps({
            "found": True,
            "files": all_requirements,
            "total_dependencies": sum(len(v) for v in all_requirements.values())
        }, indent=2)
    else:
        return create_not_found_response("requirements.txt files")


@tool
def read_pyproject_toml(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """Parse pyproject.toml for modern Python project configuration.

    Extracts project metadata, dependencies, and tool configurations from
    pyproject.toml (PEP 518/621). Supports both standard project tables and
    Poetry-specific configurations.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - found: bool - Whether pyproject.toml was found
        - path: str - Path to pyproject.toml (if found)
        - name: str - Project name
        - version: str - Project version
        - description: str - Project description
        - dependencies: list - Production dependencies
        - optional_dependencies: list - Optional dependency group names
        - tools: list - Configured tool names
        - poetry_dependencies: list - Poetry dependencies (if using Poetry)
        - poetry_dev_dependencies: list - Poetry dev dependencies (if using Poetry)
        - message: str - Status message (if not found)
        - error: str - Error message (if parsing failed)

    Example:
        >>> result = read_pyproject_toml("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["dependencies"]
        ["requests>=2.28.0", "pydantic>=2.0"]
    """
    # Check if pyproject.toml exists
    exists, pyproject_path = check_file_exists(repo_path, "pyproject.toml")
    if not exists:
        return create_not_found_response("pyproject.toml")

    # Parse TOML file
    data = parse_toml_file(pyproject_path)
    if data is None:
        return create_error_response("Failed to parse TOML", str(pyproject_path))

    # Extract and return analysis
    analysis = {"found": True, "path": str(pyproject_path)}

    # Extract standard project metadata (PEP 621)
    if "project" in data:
        project = data["project"]
        analysis["name"] = project.get("name", "")
        analysis["version"] = project.get("version", "")
        analysis["description"] = project.get("description", "")
        analysis["dependencies"] = project.get("dependencies", [])
        analysis["optional_dependencies"] = list(project.get("optional-dependencies", {}).keys())

    # Extract tool configurations
    if "tool" in data:
        tools = data["tool"]
        analysis["tools"] = list(tools.keys())

        # Extract Poetry-specific configuration
        if "poetry" in tools:
            poetry = tools["poetry"]
            analysis["poetry_dependencies"] = list(poetry.get("dependencies", {}).keys())
            analysis["poetry_dev_dependencies"] = list(poetry.get("dev-dependencies", {}).keys())

    return json.dumps(analysis, indent=2)


# ============================================================================
# LANGUAGE-SPECIFIC TOOLS: JAVA
# ============================================================================


@tool
def read_pom_xml(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """Parse pom.xml for Java/Maven project configuration.

    Extracts project metadata, dependencies, and plugin configurations from
    a Maven POM (Project Object Model) file.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - found: bool - Whether pom.xml was found
        - path: str - Path to pom.xml (if found)
        - name: str - Project name
        - version: str - Project version
        - dependencies: list - Dependency artifact IDs
        - plugins: list - Build plugin artifact IDs
        - message: str - Status message (if not found)
        - error: str - Error message (if parsing failed)

    Example:
        >>> result = read_pom_xml("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["dependencies"]
        ["spring-boot-starter-web", "junit-jupiter"]
    """
    # Check if pom.xml exists
    exists, pom_path = check_file_exists(repo_path, "pom.xml")
    if not exists:
        return create_not_found_response("pom.xml")

    # Parse XML with Maven namespace
    namespace = {"pom": "http://maven.apache.org/POM/4.0.0"}
    root = parse_xml_file(pom_path, namespace)
    if root is None:
        return create_error_response("Failed to parse XML", str(pom_path))

    try:
        analysis = {"found": True, "path": str(pom_path)}

        # Extract project metadata
        name_elem = root.find("pom:name", namespace)
        analysis["name"] = name_elem.text if name_elem is not None else ""

        version_elem = root.find("pom:version", namespace)
        analysis["version"] = version_elem.text if version_elem is not None else ""

        # Extract dependencies
        dependencies = []
        deps_elem = root.find("pom:dependencies", namespace)
        if deps_elem is not None:
            for dep in deps_elem.findall("pom:dependency", namespace):
                artifact_id = dep.find("pom:artifactId", namespace)
                if artifact_id is not None:
                    dependencies.append(artifact_id.text)
        analysis["dependencies"] = dependencies

        # Extract build plugins
        plugins = []
        plugins_elem = root.find("pom:build/pom:plugins", namespace)
        if plugins_elem is not None:
            for plugin in plugins_elem.findall("pom:plugin", namespace):
                artifact_id = plugin.find("pom:artifactId", namespace)
                if artifact_id is not None:
                    plugins.append(artifact_id.text)
        analysis["plugins"] = plugins

        return json.dumps(analysis, indent=2)

    except Exception as e:
        logger.error(f"Error processing pom.xml: {str(e)}")
        return create_error_response(f"Failed to process: {str(e)}", str(pom_path))


@tool
def read_build_gradle(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """Parse build.gradle for Java/Gradle project configuration.

    Analyzes Gradle build files (both Groovy and Kotlin DSL) to extract
    plugins, dependencies, and project properties using regex patterns.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - found: bool - Whether build.gradle was found
        - path: str - Path to build.gradle (if found)
        - file_type: str - gradle_groovy or gradle_kotlin
        - plugins: list - Applied plugin IDs
        - dependencies: list - Dependency declarations
        - properties: dict - Project properties
        - message: str - Status message (if not found)
        - error: str - Error message (if parsing failed)

    Example:
        >>> result = read_build_gradle("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["plugins"]
        ["java", "org.springframework.boot"]
    """
    # Check for both Groovy and Kotlin DSL variants
    gradle_files = ["build.gradle", "build.gradle.kts"]

    for filename in gradle_files:
        exists, gradle_path = check_file_exists(repo_path, filename)
        if exists:
            try:
                content = gradle_path.read_text()
                analysis = {
                    "found": True,
                    "path": str(gradle_path),
                    "file_type": "gradle_kotlin" if gradle_path.suffix == ".kts" else "gradle_groovy"
                }

                # Extract plugins using regex
                plugin_pattern = r'(?:apply\s+plugin:|plugins\s*\{[^}]*?\bid\s+["\'])([^"\']+)'
                plugins = list(set(re.findall(plugin_pattern, content)))
                analysis["plugins"] = plugins

                # Extract dependencies using regex
                dep_pattern = r'(?:implementation|api|testImplementation|testApi)\s+["\']([^"\']+)["\']'
                dependencies = list(set(re.findall(dep_pattern, content)))
                analysis["dependencies"] = dependencies

                # Extract properties
                prop_pattern = r'(\w+)\s*=\s+["\']([^"\']+)["\']'
                analysis["properties"] = dict(re.findall(prop_pattern, content))

                return json.dumps(analysis, indent=2)

            except Exception as e:
                logger.error(f"Error parsing {gradle_path}: {str(e)}")
                return create_error_response(f"Failed to parse: {str(e)}", str(gradle_path))

    # No build.gradle file found
    return create_not_found_response("build.gradle files")


# ============================================================================
# LANGUAGE-SPECIFIC TOOLS: GO
# ============================================================================


@tool
def read_go_mod(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """Parse go.mod for Go project module and dependency information.

    Extracts Go module name, Go version requirement, and dependency list
    from the go.mod file.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - found: bool - Whether go.mod was found
        - path: str - Path to go.mod (if found)
        - module: str - Go module name
        - go_version: str - Required Go version
        - dependencies: list - Module dependencies with versions
        - message: str - Status message (if not found)
        - error: str - Error message (if parsing failed)

    Example:
        >>> result = read_go_mod("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["module"]
        "github.com/user/project"
        >>> data["dependencies"]
        ["github.com/gin-gonic/gin@v1.9.0", "gorm.io/gorm@v1.25.0"]
    """
    # Check if go.mod exists
    exists, go_mod_path = check_file_exists(repo_path, "go.mod")
    if not exists:
        return create_not_found_response("go.mod")

    try:
        content = go_mod_path.read_text()
        analysis = {"found": True, "path": str(go_mod_path)}
        lines = content.split("\n")

        # Extract module name
        for line in lines:
            if line.startswith("module "):
                analysis["module"] = line[7:].strip()
                break

        # Extract Go version
        for line in lines:
            if line.startswith("go "):
                analysis["go_version"] = line[3:].strip()
                break

        # Extract dependencies from require block
        dependencies = []
        in_require = False
        for line in lines:
            if line.startswith("require"):
                in_require = True
                continue
            if in_require:
                if line.startswith("("):
                    continue
                if line.startswith(")"):
                    break
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        dependencies.append(f"{parts[0]}@{parts[1]}")

        analysis["dependencies"] = dependencies
        return json.dumps(analysis, indent=2)

    except Exception as e:
        logger.error(f"Error parsing go.mod: {str(e)}")
        return create_error_response(f"Failed to parse: {str(e)}", str(go_mod_path))


# ============================================================================
# LANGUAGE-SPECIFIC TOOLS: RUST
# ============================================================================


@tool
def read_cargo_toml(
    repo_path: Annotated[str, "Absolute path to the repository root directory"]
) -> str:
    """Parse Cargo.toml for Rust project configuration and dependencies.

    Extracts package metadata and dependency information from Cargo's
    manifest file, including regular, dev, and build dependencies.

    Args:
        repo_path: Absolute path to the repository root directory

    Returns:
        JSON string containing:
        - found: bool - Whether Cargo.toml was found
        - path: str - Path to Cargo.toml (if found)
        - name: str - Package name
        - version: str - Package version
        - edition: str - Rust edition (e.g., "2021")
        - description: str - Package description
        - dependencies: list - Regular dependency names
        - dev_dependencies: list - Development dependency names
        - build_dependencies: list - Build dependency names
        - message: str - Status message (if not found)
        - error: str - Error message (if parsing failed)

    Example:
        >>> result = read_cargo_toml("/path/to/repo")
        >>> data = json.loads(result)
        >>> data["dependencies"]
        ["serde", "tokio", "reqwest"]
    """
    # Check if Cargo.toml exists
    exists, cargo_path = check_file_exists(repo_path, "Cargo.toml")
    if not exists:
        return create_not_found_response("Cargo.toml")

    # Parse TOML file
    data = parse_toml_file(cargo_path)
    if data is None:
        return create_error_response("Failed to parse TOML", str(cargo_path))

    # Extract and return analysis
    analysis = {"found": True, "path": str(cargo_path)}

    # Extract package metadata
    if "package" in data:
        package = data["package"]
        analysis["name"] = package.get("name", "")
        analysis["version"] = package.get("version", "")
        analysis["edition"] = package.get("edition", "")
        analysis["description"] = package.get("description", "")

    # Extract dependencies
    analysis["dependencies"] = list(data.get("dependencies", {}).keys())
    analysis["dev_dependencies"] = list(data.get("dev-dependencies", {}).keys())
    analysis["build_dependencies"] = list(data.get("build-dependencies", {}).keys())

    return json.dumps(analysis, indent=2)
