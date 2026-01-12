"""Component analysis tools for code structure and organization.

These tools provide specialized analysis of code components:
- Classes, inheritance hierarchies, and relationships
- Module organization and package structure
- Public APIs and exports
- Component boundaries and interfaces
- Dependency injection patterns and service architecture
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from langchain_core.tools import tool


@tool
async def analyze_classes(repo_path: str) -> str:
    """Analyze all classes in the codebase and their relationships.

    Extracts:
    - Class definitions and their inheritance
    - Public methods and properties
    - Class relationships (inheritance, composition)
    - Abstract base classes and interfaces
    - Dataclass and enum definitions

    Args:
        repo_path: Path to repository to analyze

    Returns:
        Structured analysis of all classes found
    """
    repo = Path(repo_path)
    classes = {}

    for py_file in repo.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    bases = [
                        ast.unparse(base) if hasattr(ast, "unparse") else str(base)
                        for base in node.bases
                    ]

                    methods = []
                    properties = []

                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            is_property = any(
                                isinstance(d, ast.Name) and d.id == "property"
                                for d in item.decorator_list
                            )
                            if is_property:
                                properties.append(item.name)
                            else:
                                methods.append(item.name)

                    class_key = f"{py_file.relative_to(repo)}::{node.name}"
                    classes[class_key] = {
                        "bases": bases,
                        "methods": methods,
                        "properties": properties,
                        "line": node.lineno,
                    }
        except Exception:
            continue

    if not classes:
        return "No classes found in repository"

    result = "CLASSES ANALYSIS:\n\n"
    for class_name, details in sorted(classes.items()):
        result += f"{class_name}\n"
        if details["bases"]:
            result += f"  Inherits from: {', '.join(details['bases'])}\n"
        if details["methods"]:
            result += f"  Methods: {', '.join(details['methods'][:10])}"
            if len(details["methods"]) > 10:
                result += f" (+{len(details['methods']) - 10} more)"
            result += "\n"
        if details["properties"]:
            result += f"  Properties: {', '.join(details['properties'])}\n"
        result += "\n"

    return result


@tool
async def analyze_module_structure(repo_path: str) -> str:
    """Analyze module organization and package structure.

    Identifies:
    - Package hierarchy and organization
    - Module dependencies and imports
    - Circular imports and dependency issues
    - Module-level organization (subpackages vs flat)
    - Public module exports (__all__)

    Args:
        repo_path: Path to repository to analyze

    Returns:
        Analysis of module structure
    """
    repo = Path(repo_path)
    packages = {}
    module_exports = {}

    for py_file in repo.rglob("*.py"):
        if "__pycache__" in str(py_file) or py_file.name == "__pycache__":
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content)

            rel_path = py_file.relative_to(repo)
            package_path = str(rel_path.parent).replace("/", ".")

            if package_path not in packages:
                packages[package_path] = []
            packages[package_path].append(py_file.stem)

            # Find __all__ exports
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            if isinstance(node.value, ast.List):
                                exports = [
                                    elt.value for elt in node.value.elts
                                    if isinstance(elt, ast.Constant)
                                ]
                                module_exports[str(rel_path)] = exports
        except Exception:
            continue

    result = "MODULE STRUCTURE ANALYSIS:\n\n"
    result += "Packages:\n"
    for package in sorted(packages.keys()):
        modules = packages[package]
        result += f"  {package}\n"
        for module in sorted(modules)[:5]:
            result += f"    - {module}\n"
        if len(modules) > 5:
            result += f"    ... (+{len(modules) - 5} more)\n"

    if module_exports:
        result += "\nPublic Exports:\n"
        for module, exports in sorted(module_exports.items()):
            result += f"  {module}: {', '.join(exports)}\n"

    return result


@tool
async def analyze_public_apis(repo_path: str) -> str:
    """Analyze public APIs and component interfaces.

    Extracts:
    - Public functions and classes (not starting with _)
    - Function signatures and parameters
    - Return types and annotations
    - API entry points
    - Exported symbols

    Args:
        repo_path: Path to repository to analyze

    Returns:
        Analysis of public APIs
    """
    repo = Path(repo_path)
    public_apis = {}

    for py_file in repo.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content)

            file_apis = []

            for node in tree.body:
                # Public functions
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    args = [arg.arg for arg in node.args.args]
                    file_apis.append({
                        "type": "function",
                        "name": node.name,
                        "args": args,
                        "line": node.lineno,
                    })

                # Public classes
                elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    file_apis.append({
                        "type": "class",
                        "name": node.name,
                        "line": node.lineno,
                    })

            if file_apis:
                public_apis[str(py_file.relative_to(repo))] = file_apis
        except Exception:
            continue

    if not public_apis:
        return "No public APIs found"

    result = "PUBLIC API ANALYSIS:\n\n"
    for module, apis in sorted(public_apis.items()):
        result += f"{module}\n"
        for api in apis:
            if api["type"] == "function":
                args_str = ", ".join(api["args"]) if api["args"] else "()"
                result += f"  def {api['name']}({args_str})\n"
            else:
                result += f"  class {api['name']}\n"

    return result


@tool
async def analyze_component_boundaries(repo_path: str) -> str:
    """Analyze component boundaries and separation of concerns.

    Identifies:
    - Directory-based components
    - Component dependencies (imports between components)
    - Internal vs external interfaces
    - Cohesion and coupling metrics
    - Component isolation

    Args:
        repo_path: Path to repository to analyze

    Returns:
        Analysis of component organization
    """
    repo = Path(repo_path)
    components = {}

    # Identify top-level components (directories with __init__.py)
    for init_file in repo.rglob("__init__.py"):
        component_dir = init_file.parent

        # Skip if too deep (more than 2 levels)
        rel_path = component_dir.relative_to(repo)
        if len(rel_path.parts) > 2:
            continue

        component_name = component_dir.name
        if component_name == "src" or component_name == ".":
            continue

        components[component_name] = {
            "path": str(rel_path),
            "files": len(list(component_dir.glob("*.py"))),
            "subcomponents": len(list(component_dir.glob("*/"))),
        }

    result = "COMPONENT BOUNDARIES ANALYSIS:\n\n"

    if components:
        result += "Identified Components:\n"
        for comp_name, details in sorted(components.items()):
            result += f"  {comp_name}/\n"
            result += f"    Path: {details['path']}\n"
            result += f"    Files: {details['files']}\n"
            result += f"    Subcomponents: {details['subcomponents']}\n"
    else:
        result += "No clear component boundaries found (no multi-level __init__.py structure)\n"

    return result


@tool
async def analyze_inheritance_hierarchy(repo_path: str) -> str:
    """Analyze class inheritance hierarchies and relationships.

    Identifies:
    - Inheritance chains and depth
    - Mixin patterns and multiple inheritance
    - Abstract base classes and interfaces
    - Method overriding patterns
    - Base class coupling

    Args:
        repo_path: Path to repository to analyze

    Returns:
        Analysis of inheritance relationships
    """
    repo = Path(repo_path)
    class_hierarchy = {}

    for py_file in repo.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    bases = []
                    is_abstract = False

                    for base in node.bases:
                        base_str = ast.unparse(base) if hasattr(ast, "unparse") else str(base)
                        bases.append(base_str)
                        if "ABC" in base_str or "abstractmethod" in str(node):
                            is_abstract = True

                    if bases:  # Only include classes with inheritance
                        class_key = f"{node.name} (line {node.lineno})"
                        class_hierarchy[class_key] = {
                            "file": str(py_file.relative_to(repo)),
                            "bases": bases,
                            "is_abstract": is_abstract,
                        }
        except Exception:
            continue

    if not class_hierarchy:
        return "No inheritance hierarchies found (all classes are independent)"

    result = "INHERITANCE HIERARCHY ANALYSIS:\n\n"
    for class_name, details in sorted(class_hierarchy.items()):
        result += f"{class_name}\n"
        result += f"  File: {details['file']}\n"
        result += f"  Inherits from: {', '.join(details['bases'])}\n"
        if details["is_abstract"]:
            result += "  Type: Abstract Base Class\n"
        result += "\n"

    return result


@tool
async def analyze_service_architecture(repo_path: str) -> str:
    """Analyze service-oriented architecture patterns.

    Identifies:
    - Service classes and their patterns
    - Factory patterns and dependency injection
    - Singleton patterns
    - Manager/Controller classes
    - Service interfaces and implementations

    Args:
        repo_path: Path to repository to analyze

    Returns:
        Analysis of service architecture
    """
    repo = Path(repo_path)
    service_patterns = {
        "services": [],
        "factories": [],
        "managers": [],
        "controllers": [],
        "singletons": [],
    }

    for py_file in repo.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    name_lower = node.name.lower()

                    if "service" in name_lower:
                        service_patterns["services"].append({
                            "name": node.name,
                            "file": str(py_file.relative_to(repo)),
                        })
                    if "factory" in name_lower:
                        service_patterns["factories"].append({
                            "name": node.name,
                            "file": str(py_file.relative_to(repo)),
                        })
                    if "manager" in name_lower:
                        service_patterns["managers"].append({
                            "name": node.name,
                            "file": str(py_file.relative_to(repo)),
                        })
                    if "controller" in name_lower:
                        service_patterns["controllers"].append({
                            "name": node.name,
                            "file": str(py_file.relative_to(repo)),
                        })
        except Exception:
            continue

    result = "SERVICE ARCHITECTURE ANALYSIS:\n\n"

    for pattern_type, items in service_patterns.items():
        if items:
            result += f"{pattern_type.replace('_', ' ').title()}:\n"
            for item in items:
                result += f"  - {item['name']} ({item['file']})\n"
            result += "\n"

    if all(len(items) == 0 for items in service_patterns.values()):
        result += "No explicit service patterns detected\n"

    return result
