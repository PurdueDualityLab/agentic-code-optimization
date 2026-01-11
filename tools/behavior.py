"""Behavior analysis tools for code analysis.

Analyzes code behavior, logic flow, execution patterns, function interactions,
control structures, data flow, and algorithmic patterns.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Optional

from langchain_core.tools import tool


def extract_functions(code: str, language: str = "python") -> list[dict[str, Any]]:
    """Extract function definitions and signatures from code."""
    if language != "python":
        return []

    functions = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Get function signature
                args = []
                for arg in node.args.args:
                    args.append(arg.arg)

                # Get decorators
                decorators = [
                    d.id if isinstance(d, ast.Name) else ast.unparse(d)
                    for d in node.decorator_list
                ]

                # Get docstring
                docstring = ast.get_docstring(node) or ""

                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "args": args,
                    "decorators": decorators,
                    "docstring": docstring[:200],  # First 200 chars
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                })
    except SyntaxError:
        pass

    return functions


def analyze_control_flow(code: str) -> dict[str, Any]:
    """Analyze control flow structures in code."""
    control_flow = {
        "loops": {"for": 0, "while": 0},
        "conditionals": {"if": 0, "try": 0},
        "recursion": [],
        "complexity": 0,
    }

    try:
        tree = ast.parse(code)

        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                control_flow["loops"]["for"] += 1
                control_flow["complexity"] += 1
            elif isinstance(node, ast.While):
                control_flow["loops"]["while"] += 1
                control_flow["complexity"] += 1
            elif isinstance(node, ast.If):
                control_flow["conditionals"]["if"] += 1
                control_flow["complexity"] += 1
            elif isinstance(node, ast.Try):
                control_flow["conditionals"]["try"] += 1
                control_flow["complexity"] += 1
            elif isinstance(node, ast.FunctionDef):
                # Check for recursion
                func_name = node.name
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name):
                            if child.func.id == func_name:
                                control_flow["recursion"].append(func_name)
    except SyntaxError:
        pass

    control_flow["recursion"] = list(set(control_flow["recursion"]))
    return control_flow


def extract_function_calls(code: str) -> dict[str, list[str]]:
    """Extract function calls and their callers."""
    calls = {}

    try:
        tree = ast.parse(code)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name
                calls[func_name] = []

                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name):
                            calls[func_name].append(child.func.id)
                        elif isinstance(child.func, ast.Attribute):
                            calls[func_name].append(child.func.attr)

                calls[func_name] = list(set(calls[func_name]))  # Remove duplicates
    except SyntaxError:
        pass

    return calls


def identify_patterns(code: str) -> dict[str, list[str]]:
    """Identify common design patterns in code."""
    patterns = {
        "singletons": [],
        "decorators_used": [],
        "context_managers": [],
        "generators": [],
        "lambda_functions": 0,
        "list_comprehensions": 0,
    }

    try:
        tree = ast.parse(code)

        # Find decorators used
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    dec_name = ""
                    if isinstance(decorator, ast.Name):
                        dec_name = decorator.id
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name):
                            dec_name = decorator.func.id
                    if dec_name and dec_name not in patterns["decorators_used"]:
                        patterns["decorators_used"].append(dec_name)

            # Count lambdas
            elif isinstance(node, ast.Lambda):
                patterns["lambda_functions"] += 1

            # Count comprehensions
            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
                patterns["list_comprehensions"] += 1

            # Find generators
            elif isinstance(node, ast.FunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Yield):
                        if node.name not in patterns["generators"]:
                            patterns["generators"].append(node.name)
                        break

        # Heuristic for context managers (with statements)
        with_count = sum(1 for _ in ast.walk(tree) if isinstance(_, ast.With))
        if with_count > 0:
            patterns["context_managers"] = [f"Found {with_count} context managers"]

    except SyntaxError:
        pass

    return patterns


def analyze_error_handling(code: str) -> dict[str, Any]:
    """Analyze error handling patterns in code."""
    error_handling = {
        "try_except_blocks": 0,
        "caught_exceptions": [],
        "raise_statements": 0,
        "bare_except": False,
    }

    try:
        tree = ast.parse(code)

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                error_handling["try_except_blocks"] += 1
                for handler in node.handlers:
                    if handler.type is None:
                        error_handling["bare_except"] = True
                    elif isinstance(handler.type, ast.Name):
                        error_handling["caught_exceptions"].append(handler.type.id)
                    elif isinstance(handler.type, ast.Tuple):
                        for exc in handler.type.elts:
                            if isinstance(exc, ast.Name):
                                error_handling["caught_exceptions"].append(exc.id)
            elif isinstance(node, ast.Raise):
                error_handling["raise_statements"] += 1

        error_handling["caught_exceptions"] = list(set(error_handling["caught_exceptions"]))
    except SyntaxError:
        pass

    return error_handling


def analyze_data_flow(code: str) -> dict[str, Any]:
    """Analyze variable dependencies and data flow."""
    data_flow = {
        "global_variables": [],
        "class_definitions": [],
        "imports": [],
        "external_dependencies": 0,
    }

    try:
        tree = ast.parse(code)

        for node in ast.walk(tree):
            # Collect global variables (assignments at module level)
            if isinstance(node, ast.Module):
                for child in node.body:
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Name):
                                data_flow["global_variables"].append(target.id)
                    elif isinstance(child, ast.ClassDef):
                        data_flow["class_definitions"].append(child.name)
                    elif isinstance(child, (ast.Import, ast.ImportFrom)):
                        data_flow["external_dependencies"] += 1
                        if isinstance(child, ast.Import):
                            for alias in child.names:
                                data_flow["imports"].append(alias.name)
                        else:
                            data_flow["imports"].append(child.module or "")

        data_flow["imports"] = [i for i in data_flow["imports"] if i]
    except SyntaxError:
        pass

    return data_flow


def detect_performance_issues(code: str) -> dict[str, list[str]]:
    """Detect potential performance issues in code."""
    issues = {
        "nested_loops": [],
        "string_concatenation_in_loop": [],
        "unnecessary_imports": [],
        "large_data_structures": [],
    }

    try:
        tree = ast.parse(code)
        loop_depth = 0
        in_loop = False

        for node in ast.walk(tree):
            # Detect nested loops
            if isinstance(node, (ast.For, ast.While)):
                loop_depth += 1
                if loop_depth > 1:
                    issues["nested_loops"].append(f"Nested loop at line {node.lineno}")
                in_loop = True

            # Detect string concatenation in loops (using regex on code)
            if in_loop and isinstance(node, ast.BinOp):
                if isinstance(node.op, ast.Add):
                    if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                        issues["string_concatenation_in_loop"].append(
                            f"String concat at line {node.lineno}"
                        )

            # Detect list/dict creations (potential large data structures)
            if isinstance(node, (ast.List, ast.Dict)):
                if hasattr(node, "lineno") and len(getattr(node, "elts", [])) > 100:
                    issues["large_data_structures"].append(f"Large structure at line {node.lineno}")

    except SyntaxError:
        pass

    return issues


def extract_docstrings(code: str) -> dict[str, str]:
    """Extract all docstrings from code."""
    docstrings = {"module": "", "functions": {}, "classes": {}}

    try:
        tree = ast.parse(code)

        # Module docstring
        module_doc = ast.get_docstring(tree)
        if module_doc:
            docstrings["module"] = module_doc[:300]

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                doc = ast.get_docstring(node)
                if doc:
                    docstrings["functions"][node.name] = doc[:200]
            elif isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                if doc:
                    docstrings["classes"][node.name] = doc[:200]
    except SyntaxError:
        pass

    return docstrings


def extract_code_from_file(file_path: str) -> str:
    """Read code from a file."""
    try:
        return Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


@tool
def analyze_functions(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Extract and analyze function definitions and signatures.

    Args:
        code: Source code to analyze
        file_path: Path to code file to analyze

    Returns:
        JSON string with function definitions and signatures
    """
    if file_path and not code:
        code = extract_code_from_file(file_path)

    if not code:
        return json.dumps({"error": "No code provided"})

    functions = extract_functions(code)
    return json.dumps({"functions": functions, "count": len(functions)}, indent=2)


@tool
def analyze_code_structure(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Analyze overall code structure including control flow, data flow, and patterns.

    Args:
        code: Source code to analyze
        file_path: Path to code file to analyze

    Returns:
        JSON string with comprehensive code structure analysis
    """
    if file_path and not code:
        code = extract_code_from_file(file_path)

    if not code:
        return json.dumps({"error": "No code provided"})

    return json.dumps({
        "functions": extract_functions(code),
        "control_flow": analyze_control_flow(code),
        "patterns": identify_patterns(code),
        "data_flow": analyze_data_flow(code),
    }, indent=2)


@tool
def analyze_function_interactions(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Extract function call graph and analyze interactions between functions.

    Args:
        code: Source code to analyze
        file_path: Path to code file to analyze

    Returns:
        JSON string with function call relationships
    """
    if file_path and not code:
        code = extract_code_from_file(file_path)

    if not code:
        return json.dumps({"error": "No code provided"})

    calls = extract_function_calls(code)
    return json.dumps({"function_calls": calls}, indent=2)


@tool
def identify_code_patterns(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Identify design patterns and code idioms used.

    Args:
        code: Source code to analyze
        file_path: Path to code file to analyze

    Returns:
        JSON string with detected patterns
    """
    if file_path and not code:
        code = extract_code_from_file(file_path)

    if not code:
        return json.dumps({"error": "No code provided"})

    return json.dumps(identify_patterns(code), indent=2)


@tool
def analyze_error_handling_strategy(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Analyze error handling patterns and exception strategies.

    Args:
        code: Source code to analyze
        file_path: Path to code file to analyze

    Returns:
        JSON string with error handling analysis
    """
    if file_path and not code:
        code = extract_code_from_file(file_path)

    if not code:
        return json.dumps({"error": "No code provided"})

    return json.dumps(analyze_error_handling(code), indent=2)


@tool
def analyze_data_dependencies(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Analyze variable dependencies and data flow.

    Args:
        code: Source code to analyze
        file_path: Path to code file to analyze

    Returns:
        JSON string with data flow and dependency analysis
    """
    if file_path and not code:
        code = extract_code_from_file(file_path)

    if not code:
        return json.dumps({"error": "No code provided"})

    return json.dumps(analyze_data_flow(code), indent=2)


@tool
def detect_performance_bottlenecks(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Detect potential performance issues and bottlenecks.

    Args:
        code: Source code to analyze
        file_path: Path to code file to analyze

    Returns:
        JSON string with detected performance issues
    """
    if file_path and not code:
        code = extract_code_from_file(file_path)

    if not code:
        return json.dumps({"error": "No code provided"})

    return json.dumps(detect_performance_issues(code), indent=2)


@tool
def extract_code_documentation(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Extract and analyze docstrings and code documentation.

    Args:
        code: Source code to analyze
        file_path: Path to code file to analyze

    Returns:
        JSON string with extracted documentation
    """
    if file_path and not code:
        code = extract_code_from_file(file_path)

    if not code:
        return json.dumps({"error": "No code provided"})

    return json.dumps(extract_docstrings(code), indent=2)


@tool
def analyze_code_complexity(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Analyze code complexity metrics including cyclomatic complexity indicators.

    Args:
        code: Source code to analyze
        file_path: Path to code file to analyze

    Returns:
        JSON string with complexity metrics
    """
    if file_path and not code:
        code = extract_code_from_file(file_path)

    if not code:
        return json.dumps({"error": "No code provided"})

    control_flow = analyze_control_flow(code)
    functions = extract_functions(code)

    return json.dumps({
        "cyclomatic_complexity": control_flow["complexity"],
        "function_count": len(functions),
        "has_recursion": len(control_flow["recursion"]) > 0,
        "recursive_functions": control_flow["recursion"],
        "control_flow": control_flow,
    }, indent=2)
