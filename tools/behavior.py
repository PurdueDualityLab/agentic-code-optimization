"""Behavior analysis tools for code analysis.

Analyzes code behavior, logic flow, execution patterns, function interactions,
control structures, data flow, and algorithmic patterns.
"""

from __future__ import annotations

import asyncio

import ast
import json
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool


@tool
async def analyze_functions(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Extract and analyze function definitions and signatures."""
    if file_path and not code:
        try:
            code = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            code = ""

    if not code:
        return json.dumps({"error": "No code provided"})

    functions = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args = [arg.arg for arg in node.args.args]
                decorators = [
                    d.id if isinstance(d, ast.Name) else ast.unparse(d)
                    for d in node.decorator_list
                ]
                docstring = ast.get_docstring(node) or ""
                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "args": args,
                    "decorators": decorators,
                    "docstring": docstring[:200],
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                })
    except SyntaxError:
        pass

    return json.dumps({"functions": functions, "count": len(functions)}, indent=2)


@tool
async def analyze_code_structure(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Analyze overall code structure including control flow, data flow, and patterns."""
    if file_path and not code:
        try:
            code = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            code = ""

    if not code:
        return json.dumps({"error": "No code provided"})

    # Extract functions
    functions = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args = [arg.arg for arg in node.args.args]
                decorators = [
                    d.id if isinstance(d, ast.Name) else ast.unparse(d)
                    for d in node.decorator_list
                ]
                docstring = ast.get_docstring(node) or ""
                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "args": args,
                    "decorators": decorators,
                    "docstring": docstring[:200],
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                })
    except SyntaxError:
        pass

    # Analyze control flow
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
                func_name = node.name
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name):
                            if child.func.id == func_name:
                                control_flow["recursion"].append(func_name)
        control_flow["recursion"] = list(set(control_flow["recursion"]))
    except SyntaxError:
        pass

    # Identify patterns
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
            elif isinstance(node, ast.Lambda):
                patterns["lambda_functions"] += 1
            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
                patterns["list_comprehensions"] += 1
            elif isinstance(node, ast.FunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Yield):
                        if node.name not in patterns["generators"]:
                            patterns["generators"].append(node.name)
                        break
        with_count = sum(1 for _ in ast.walk(tree) if isinstance(_, ast.With))
        if with_count > 0:
            patterns["context_managers"] = [f"Found {with_count} context managers"]
    except SyntaxError:
        pass

    # Analyze data flow
    data_flow = {
        "global_variables": [],
        "class_definitions": [],
        "imports": [],
        "external_dependencies": 0,
    }
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
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

    return json.dumps({
        "functions": functions,
        "control_flow": control_flow,
        "patterns": patterns,
        "data_flow": data_flow,
    }, indent=2)


@tool
async def analyze_function_interactions(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Extract function call graph and analyze interactions between functions."""
    if file_path and not code:
        try:
            code = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            code = ""

    if not code:
        return json.dumps({"error": "No code provided"})

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
                calls[func_name] = list(set(calls[func_name]))
    except SyntaxError:
        pass

    return json.dumps({"function_calls": calls}, indent=2)


@tool
async def identify_code_patterns(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Identify design patterns and code idioms used."""
    if file_path and not code:
        try:
            code = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            code = ""

    if not code:
        return json.dumps({"error": "No code provided"})

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
            elif isinstance(node, ast.Lambda):
                patterns["lambda_functions"] += 1
            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
                patterns["list_comprehensions"] += 1
            elif isinstance(node, ast.FunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Yield):
                        if node.name not in patterns["generators"]:
                            patterns["generators"].append(node.name)
                        break
        with_count = sum(1 for _ in ast.walk(tree) if isinstance(_, ast.With))
        if with_count > 0:
            patterns["context_managers"] = [f"Found {with_count} context managers"]
    except SyntaxError:
        pass

    return json.dumps(patterns, indent=2)


@tool
async def analyze_error_handling_strategy(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Analyze error handling patterns and exception strategies."""
    if file_path and not code:
        try:
            code = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            code = ""

    if not code:
        return json.dumps({"error": "No code provided"})

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

    return json.dumps(error_handling, indent=2)


@tool
async def analyze_data_dependencies(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Analyze variable dependencies and data flow."""
    if file_path and not code:
        try:
            code = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            code = ""

    if not code:
        return json.dumps({"error": "No code provided"})

    data_flow = {
        "global_variables": [],
        "class_definitions": [],
        "imports": [],
        "external_dependencies": 0,
    }
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
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

    return json.dumps(data_flow, indent=2)


@tool
async def detect_performance_bottlenecks(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Detect potential performance issues and bottlenecks."""
    if file_path and not code:
        try:
            code = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            code = ""

    if not code:
        return json.dumps({"error": "No code provided"})

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
            if isinstance(node, (ast.For, ast.While)):
                loop_depth += 1
                if loop_depth > 1:
                    issues["nested_loops"].append(f"Nested loop at line {node.lineno}")
                in_loop = True

            if in_loop and isinstance(node, ast.BinOp):
                if isinstance(node.op, ast.Add):
                    if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                        issues["string_concatenation_in_loop"].append(
                            f"String concat at line {node.lineno}"
                        )

            if isinstance(node, (ast.List, ast.Dict)):
                if hasattr(node, "lineno") and len(getattr(node, "elts", [])) > 100:
                    issues["large_data_structures"].append(f"Large structure at line {node.lineno}")
    except SyntaxError:
        pass

    return json.dumps(issues, indent=2)


@tool
async def extract_code_documentation(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Extract and analyze docstrings and code documentation."""
    if file_path and not code:
        try:
            code = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            code = ""

    if not code:
        return json.dumps({"error": "No code provided"})

    docstrings = {"module": "", "functions": {}, "classes": {}}
    try:
        tree = ast.parse(code)
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

    return json.dumps(docstrings, indent=2)


@tool
async def analyze_code_complexity(code: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Analyze code complexity metrics including cyclomatic complexity indicators."""
    if file_path and not code:
        try:
            code = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            code = ""

    if not code:
        return json.dumps({"error": "No code provided"})

    # Extract functions
    functions = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args = [arg.arg for arg in node.args.args]
                decorators = [
                    d.id if isinstance(d, ast.Name) else ast.unparse(d)
                    for d in node.decorator_list
                ]
                docstring = ast.get_docstring(node) or ""
                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "args": args,
                    "decorators": decorators,
                    "docstring": docstring[:200],
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                })
    except SyntaxError:
        pass

    # Analyze control flow
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
                func_name = node.name
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name):
                            if child.func.id == func_name:
                                control_flow["recursion"].append(func_name)
        control_flow["recursion"] = list(set(control_flow["recursion"]))
    except SyntaxError:
        pass

    return json.dumps({
        "cyclomatic_complexity": control_flow["complexity"],
        "function_count": len(functions),
        "has_recursion": len(control_flow["recursion"]) > 0,
        "recursive_functions": control_flow["recursion"],
        "control_flow": control_flow,
    }, indent=2)
