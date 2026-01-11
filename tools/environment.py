"""Tools for EnvironmentSummarizer agent - all code self-contained."""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ============================================================================
# File Discovery & Analysis
# ============================================================================

def detect_git_config(repo_root: str) -> dict[str, Any]:
    """Detect Git configuration and repository information."""
    git_dir = Path(repo_root) / ".git"
    if not git_dir.exists():
        return {"found": False, "message": "Git repository not detected"}

    try:
        analysis = {"found": True, "path": str(git_dir)}
        if (git_dir / "bare").exists():
            analysis["is_bare"] = True

        config_path = git_dir / "config"
        if config_path.exists():
            content = config_path.read_text()
            analysis["has_config"] = True
            for line in content.split("\n"):
                if "url = " in line:
                    analysis["remote_url"] = line.split("url = ")[1].strip()
                    break

        analysis["has_hooks"] = (git_dir / "hooks").exists()
        analysis["has_objects"] = (git_dir / "objects").exists()
        analysis["has_refs"] = (git_dir / "refs").exists()
        analysis["has_gitignore"] = (Path(repo_root) / ".gitignore").exists()
        return analysis
    except Exception as e:
        logger.error(f"Error analyzing Git config: {str(e)}")
        return {"found": True, "error": f"Failed to analyze: {str(e)}", "path": str(git_dir)}


def list_config_files(repo_root: str) -> dict[str, Any]:
    """List all configuration files found in the repository root."""
    config_patterns = {
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

    found_configs = {category: [] for category in config_patterns}
    root_path = Path(repo_root)

    for category, patterns in config_patterns.items():
        for pattern in patterns:
            if (root_path / pattern).exists():
                found_configs[category].append(pattern)

    total_found = sum(len(items) for items in found_configs.values())
    return {"found": total_found > 0, "total_config_files": total_found, "config_files_by_category": found_configs}


def analyze_directory_structure(repo_root: str, max_depth: int = 3) -> dict[str, Any]:
    """Analyze directory structure to identify project type and organization."""
    try:
        root_path = Path(repo_root)
        analysis = {"found": True, "path": str(root_path), "max_depth": max_depth}

        top_dirs = [item.name for item in root_path.iterdir() if item.is_dir() and not item.name.startswith(".")]
        analysis["top_level_directories"] = sorted(top_dirs)

        project_markers = {}
        for pattern in ["src", "lib", "source", "code"]:
            if pattern in top_dirs:
                project_markers[f"has_{pattern}_dir"] = True

        test_patterns = ["test", "tests", "spec", "specs", "__tests__"]
        test_dirs = [d for d in top_dirs if any(p in d for p in test_patterns)]
        project_markers["test_directories"] = test_dirs

        doc_patterns = ["doc", "docs", "documentation", "wiki"]
        doc_dirs = [d for d in top_dirs if any(p in d for p in doc_patterns)]
        project_markers["documentation_directories"] = doc_dirs

        example_patterns = ["example", "examples", "sample", "samples"]
        example_dirs = [d for d in top_dirs if any(p in d for p in example_patterns)]
        project_markers["example_directories"] = example_dirs

        file_extensions = {}
        for item in root_path.iterdir():
            if item.is_file():
                ext = item.suffix or "no_extension"
                file_extensions[ext] = file_extensions.get(ext, 0) + 1

        analysis["file_extensions_at_root"] = file_extensions
        analysis["project_markers"] = project_markers

        monorepo_indicators = {
            "workspaces": (root_path / "package.json").exists(),
            "lerna": (root_path / "lerna.json").exists(),
            "yarn_workspaces": any((root_path / d).exists() for d in ["packages", "apps"]),
        }
        analysis["monorepo_indicators"] = monorepo_indicators

        subdirs_analysis = {}
        for directory in sorted(top_dirs)[:10]:
            dir_path = root_path / directory
            file_count = sum(1 for _ in dir_path.rglob("*") if _.is_file())
            subdirs_analysis[directory] = {"file_count": min(file_count, 1000)}

        analysis["subdirectories"] = subdirs_analysis
        return analysis
    except Exception as e:
        logger.error(f"Error analyzing directory structure: {str(e)}")
        return {"found": False, "error": f"Failed to analyze: {str(e)}"}


# ============================================================================
# Configuration Parsers
# ============================================================================

def parse_dockerfile(repo_root: str) -> dict[str, Any]:
    """Parse Dockerfile to extract base image, exposed ports, and environment variables."""
    dockerfile_path = Path(repo_root) / "Dockerfile"
    if not dockerfile_path.exists():
        return {"found": False, "message": "Dockerfile not found"}

    try:
        content = dockerfile_path.read_text()
        analysis = {"found": True, "path": str(dockerfile_path)}

        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("FROM "):
                analysis["base_image"] = line[5:].split()[0]
                break

        exposed_ports = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("EXPOSE "):
                exposed_ports.extend(line[7:].split())
        analysis["exposed_ports"] = exposed_ports

        env_vars = {}
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("ENV "):
                env_part = line[4:]
                if "=" in env_part:
                    key, value = env_part.split("=", 1)
                    env_vars[key.strip()] = value.strip()
        analysis["environment_variables"] = env_vars
        analysis["raw_content"] = content[:500]
        analysis["total_lines"] = len(content.split("\n"))
        return analysis
    except Exception as e:
        logger.error(f"Error parsing Dockerfile: {str(e)}")
        return {"found": True, "error": f"Failed to parse: {str(e)}", "path": str(dockerfile_path)}


def parse_docker_compose(repo_root: str) -> dict[str, Any]:
    """Parse docker-compose.yml to extract services and configuration."""
    compose_paths = [Path(repo_root) / f for f in ["docker-compose.yml", "docker-compose.yaml", "compose.yml"]]

    for compose_path in compose_paths:
        if compose_path.exists():
            try:
                import yaml
                with open(compose_path) as f:
                    data = yaml.safe_load(f)

                if not isinstance(data, dict):
                    return {"found": False, "message": "Invalid docker-compose format"}

                analysis = {"found": True, "path": str(compose_path), "version": data.get("version", "unknown")}
                services = data.get("services", {})
                analysis["services"] = list(services.keys()) if isinstance(services, dict) else []

                env_vars = {}
                if isinstance(services, dict):
                    for service_name, service_config in services.items():
                        if isinstance(service_config, dict) and "environment" in service_config:
                            env = service_config.get("environment", {})
                            if isinstance(env, dict):
                                env_vars.update(env)
                            elif isinstance(env, list):
                                for item in env:
                                    if "=" in item:
                                        k, v = item.split("=", 1)
                                        env_vars[k] = v

                analysis["environment_variables"] = env_vars
                analysis["volumes"] = data.get("volumes", {})
                return analysis
            except Exception as e:
                logger.error(f"Error parsing {compose_path}: {str(e)}")
                return {"found": True, "error": f"Failed to parse: {str(e)}", "path": str(compose_path)}

    return {"found": False, "message": "docker-compose files not found"}


def parse_dotenv(repo_root: str) -> dict[str, Any]:
    """Parse .env files to extract environment variables."""
    env_files = [Path(repo_root) / f for f in [".env", ".env.local", ".env.example"]]
    all_vars = {}
    found_files = []

    for env_file in env_files:
        if env_file.exists():
            try:
                content = env_file.read_text()
                found_files.append(str(env_file))
                for line in content.split("\n"):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        all_vars[key.strip()] = value.strip()
            except Exception as e:
                logger.error(f"Error parsing {env_file}: {str(e)}")

    return {"found": True, "files": found_files, "variables": all_vars} if found_files else {"found": False, "message": ".env files not found"}


def parse_package_json(repo_root: str) -> dict[str, Any]:
    """Parse package.json to extract Node.js dependencies and configuration."""
    package_json_path = Path(repo_root) / "package.json"
    if not package_json_path.exists():
        return {"found": False, "message": "package.json not found"}

    try:
        with open(package_json_path) as f:
            data = json.load(f)

        analysis = {
            "found": True, "path": str(package_json_path), "name": data.get("name", ""),
            "version": data.get("version", ""), "description": data.get("description", ""),
            "type": data.get("type", "commonjs"),
            "dependencies": list(data.get("dependencies", {}).keys()),
            "dev_dependencies": list(data.get("devDependencies", {}).keys()),
            "peer_dependencies": list(data.get("peerDependencies", {}).keys()),
            "scripts": list(data.get("scripts", {}).keys()),
            "engines": data.get("engines", {}),
            "author": data.get("author", ""),
            "license": data.get("license", ""),
        }
        return analysis
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing package.json: {str(e)}")
        return {"found": True, "error": f"Invalid JSON: {str(e)}", "path": str(package_json_path)}
    except Exception as e:
        logger.error(f"Error reading package.json: {str(e)}")
        return {"found": False, "error": str(e)}


def parse_requirements_txt(repo_root: str) -> dict[str, Any]:
    """Parse requirements.txt to extract Python dependencies."""
    req_files = [Path(repo_root) / f for f in ["requirements.txt", "requirements-dev.txt", "requirements-prod.txt"]]
    all_requirements = {}

    for req_file in req_files:
        if req_file.exists():
            try:
                content = req_file.read_text()
                packages = []
                for line in content.split("\n"):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    pkg = re.split(r'[\[\>=<~!]', line)[0].strip()
                    if pkg:
                        packages.append(pkg)
                all_requirements[req_file.name] = packages
            except Exception as e:
                logger.error(f"Error parsing {req_file}: {str(e)}")

    return {"found": True, "files": all_requirements, "total_dependencies": sum(len(v) for v in all_requirements.values())} if all_requirements else {"found": False, "message": "requirements.txt files not found"}


def parse_pyproject_toml(repo_root: str) -> dict[str, Any]:
    """Parse pyproject.toml to extract Python project configuration."""
    pyproject_path = Path(repo_root) / "pyproject.toml"
    if not pyproject_path.exists():
        return {"found": False, "message": "pyproject.toml not found"}

    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            logger.warning("tomli not available")
            return {"found": True, "error": "TOML parser not available", "path": str(pyproject_path)}

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        analysis = {"found": True, "path": str(pyproject_path)}
        if "project" in data:
            project = data["project"]
            analysis["name"] = project.get("name", "")
            analysis["version"] = project.get("version", "")
            analysis["description"] = project.get("description", "")
            analysis["dependencies"] = project.get("dependencies", [])
            analysis["optional_dependencies"] = list(project.get("optional-dependencies", {}).keys())

        if "tool" in data:
            tools = data["tool"]
            analysis["tools"] = list(tools.keys())
            if "poetry" in tools:
                poetry = tools["poetry"]
                analysis["poetry_dependencies"] = list(poetry.get("dependencies", {}).keys())
                analysis["poetry_dev_dependencies"] = list(poetry.get("dev-dependencies", {}).keys())

        return analysis
    except Exception as e:
        logger.error(f"Error parsing pyproject.toml: {str(e)}")
        return {"found": True, "error": f"Failed to parse: {str(e)}", "path": str(pyproject_path)}


def parse_maven_pom(repo_root: str) -> dict[str, Any]:
    """Parse pom.xml to extract Maven project configuration."""
    pom_path = Path(repo_root) / "pom.xml"
    if not pom_path.exists():
        return {"found": False, "message": "pom.xml not found"}

    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
        namespace = {"pom": "http://maven.apache.org/POM/4.0.0"}

        analysis = {"found": True, "path": str(pom_path)}
        name_elem = root.find("pom:name", namespace)
        analysis["name"] = name_elem.text if name_elem is not None else ""
        version_elem = root.find("pom:version", namespace)
        analysis["version"] = version_elem.text if version_elem is not None else ""

        dependencies = []
        deps_elem = root.find("pom:dependencies", namespace)
        if deps_elem is not None:
            for dep in deps_elem.findall("pom:dependency", namespace):
                artifact_id = dep.find("pom:artifactId", namespace)
                if artifact_id is not None:
                    dependencies.append(artifact_id.text)

        analysis["dependencies"] = dependencies

        plugins = []
        plugins_elem = root.find("pom:build/pom:plugins", namespace)
        if plugins_elem is not None:
            for plugin in plugins_elem.findall("pom:plugin", namespace):
                artifact_id = plugin.find("pom:artifactId", namespace)
                if artifact_id is not None:
                    plugins.append(artifact_id.text)

        analysis["plugins"] = plugins
        return analysis
    except Exception as e:
        logger.error(f"Error parsing pom.xml: {str(e)}")
        return {"found": True, "error": f"Failed to parse: {str(e)}", "path": str(pom_path)}


def parse_gradle_build(repo_root: str) -> dict[str, Any]:
    """Parse build.gradle to extract Gradle project configuration."""
    gradle_files = [Path(repo_root) / f for f in ["build.gradle", "build.gradle.kts"]]

    for gradle_path in gradle_files:
        if gradle_path.exists():
            try:
                content = gradle_path.read_text()
                analysis = {"found": True, "path": str(gradle_path), "file_type": "gradle_kotlin" if gradle_path.suffix == ".kts" else "gradle_groovy"}

                plugin_pattern = r'(?:apply\s+plugin:|plugins\s*\{[^}]*?\bid\s+["\'])([^"\']+)'
                plugins = list(set(re.findall(plugin_pattern, content)))
                analysis["plugins"] = plugins

                dep_pattern = r'(?:implementation|api|testImplementation|testApi)\s+["\']([^"\']+)["\']'
                dependencies = list(set(re.findall(dep_pattern, content)))
                analysis["dependencies"] = dependencies

                prop_pattern = r'(\w+)\s*=\s*["\']([^"\']+)["\']'
                analysis["properties"] = dict(re.findall(prop_pattern, content))

                return analysis
            except Exception as e:
                logger.error(f"Error parsing {gradle_path}: {str(e)}")
                return {"found": True, "error": f"Failed to parse: {str(e)}", "path": str(gradle_path)}

    return {"found": False, "message": "build.gradle files not found"}


def parse_go_mod(repo_root: str) -> dict[str, Any]:
    """Parse go.mod to extract Go module configuration."""
    go_mod_path = Path(repo_root) / "go.mod"
    if not go_mod_path.exists():
        return {"found": False, "message": "go.mod not found"}

    try:
        content = go_mod_path.read_text()
        analysis = {"found": True, "path": str(go_mod_path)}

        lines = content.split("\n")
        for line in lines:
            if line.startswith("module "):
                analysis["module"] = line[7:].strip()
                break

        for line in lines:
            if line.startswith("go "):
                analysis["go_version"] = line[3:].strip()
                break

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
        return analysis
    except Exception as e:
        logger.error(f"Error parsing go.mod: {str(e)}")
        return {"found": True, "error": f"Failed to parse: {str(e)}", "path": str(go_mod_path)}


def parse_cargo_toml(repo_root: str) -> dict[str, Any]:
    """Parse Cargo.toml to extract Rust project configuration."""
    cargo_path = Path(repo_root) / "Cargo.toml"
    if not cargo_path.exists():
        return {"found": False, "message": "Cargo.toml not found"}

    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            logger.warning("tomli not available")
            return {"found": True, "error": "TOML parser not available", "path": str(cargo_path)}

    try:
        with open(cargo_path, "rb") as f:
            data = tomllib.load(f)

        analysis = {"found": True, "path": str(cargo_path)}
        if "package" in data:
            package = data["package"]
            analysis["name"] = package.get("name", "")
            analysis["version"] = package.get("version", "")
            analysis["edition"] = package.get("edition", "")
            analysis["description"] = package.get("description", "")

        analysis["dependencies"] = list(data.get("dependencies", {}).keys())
        analysis["dev_dependencies"] = list(data.get("dev-dependencies", {}).keys())
        analysis["build_dependencies"] = list(data.get("build-dependencies", {}).keys())
        return analysis
    except Exception as e:
        logger.error(f"Error parsing Cargo.toml: {str(e)}")
        return {"found": True, "error": f"Failed to parse: {str(e)}", "path": str(cargo_path)}


# ============================================================================
# Tool Functions with @tool Decorator
# ============================================================================

@tool
def list_repo_config_files(repo_path: str) -> str:
    """List all configuration files found in repository root."""
    result = list_config_files(repo_path)
    return json.dumps(result, indent=2)


@tool
def analyze_repo_structure(repo_path: str) -> str:
    """Analyze repository directory structure to identify project type."""
    result = analyze_directory_structure(repo_path, max_depth=3)
    return json.dumps(result, indent=2)


@tool
def check_git_config(repo_path: str) -> str:
    """Detect and analyze Git configuration."""
    result = detect_git_config(repo_path)
    return json.dumps(result, indent=2)


@tool
def read_package_json(repo_path: str) -> str:
    """Parse package.json (Node.js/JavaScript)."""
    result = parse_package_json(repo_path)
    return json.dumps(result, indent=2)


@tool
def read_requirements_txt(repo_path: str) -> str:
    """Parse requirements.txt files (Python)."""
    result = parse_requirements_txt(repo_path)
    return json.dumps(result, indent=2)


@tool
def read_pyproject_toml(repo_path: str) -> str:
    """Parse pyproject.toml (Modern Python)."""
    result = parse_pyproject_toml(repo_path)
    return json.dumps(result, indent=2)


@tool
def read_dockerfile(repo_path: str) -> str:
    """Parse Dockerfile for container configuration."""
    result = parse_dockerfile(repo_path)
    return json.dumps(result, indent=2)


@tool
def read_docker_compose(repo_path: str) -> str:
    """Parse docker-compose.yml for multi-container setup."""
    result = parse_docker_compose(repo_path)
    return json.dumps(result, indent=2)


@tool
def read_env_files(repo_path: str) -> str:
    """Parse .env files for environment configuration."""
    result = parse_dotenv(repo_path)
    return json.dumps(result, indent=2)


@tool
def read_pom_xml(repo_path: str) -> str:
    """Parse pom.xml (Java/Maven)."""
    result = parse_maven_pom(repo_path)
    return json.dumps(result, indent=2)


@tool
def read_build_gradle(repo_path: str) -> str:
    """Parse build.gradle (Java/Gradle)."""
    result = parse_gradle_build(repo_path)
    return json.dumps(result, indent=2)


@tool
def read_go_mod(repo_path: str) -> str:
    """Parse go.mod (Go)."""
    result = parse_go_mod(repo_path)
    return json.dumps(result, indent=2)


@tool
def read_cargo_toml(repo_path: str) -> str:
    """Parse Cargo.toml (Rust)."""
    result = parse_cargo_toml(repo_path)
    return json.dumps(result, indent=2)
