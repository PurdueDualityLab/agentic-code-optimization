"""Run static analysis tools and emit normalized JSON output."""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.tools import tool

from .config_analyzer import ConfigAnalyzer
from .native_deps_analyzer import NativeDependencyAnalyzer
from .noir_analyzer import NoirAnalyzer
from .python_analyzer import PythonAnalyzer
from .semgrep_analyzer import SemgrepAnalyzer
from .treesitter_analyzer import TreeSitterAnalyzer
from .utils import build_inventory, dedupe_items, limit_items, safe_run, which


def _count_by(items: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for item in items:
        value = item.get(key)
        if value:
            counter[str(value)] += 1
    return dict(counter)


def _merge_list(target: List[Dict[str, Any]], items: List[Dict[str, Any]], source: str | None = None) -> None:
    for item in items:
        if source and "source" not in item:
            item["source"] = source
        target.append(item)


def _tool_versions() -> Dict[str, str]:
    versions: Dict[str, str] = {
        "python": sys.version.split()[0],
    }

    if which("semgrep"):
        _code, stdout, _stderr = safe_run(["semgrep", "--version"], 5)
        versions["semgrep"] = stdout.strip().splitlines()[0] if stdout else "unknown"

    if which("noir"):
        _code, stdout, _stderr = safe_run(["noir", "--version"], 5)
        versions["noir"] = stdout.strip().splitlines()[0] if stdout else "unknown"

    if which("pyright"):
        _code, stdout, _stderr = safe_run(["pyright", "--version"], 5)
        versions["pyright"] = stdout.strip().splitlines()[0] if stdout else "unknown"

    if which("mypy"):
        _code, stdout, _stderr = safe_run(["mypy", "--version"], 5)
        versions["mypy"] = stdout.strip().splitlines()[0] if stdout else "unknown"

    try:
        import tree_sitter_languages  # type: ignore

        versions["tree_sitter_languages"] = getattr(tree_sitter_languages, "__version__", "unknown")
    except Exception:
        versions["tree_sitter_languages"] = "not_installed"

    return versions


def _file_hotspots(
    endpoints: List[Dict[str, Any]],
    http_clients: List[Dict[str, Any]],
    grpc_clients: List[Dict[str, Any]],
    queue_clients: List[Dict[str, Any]],
    database_clients: List[Dict[str, Any]],
    cache_clients: List[Dict[str, Any]],
    storage_clients: List[Dict[str, Any]],
    security: List[Dict[str, Any]],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    buckets: Dict[str, Dict[str, int]] = {}

    def add(item: Dict[str, Any], key: str) -> None:
        file_path = item.get("file")
        if not file_path:
            return
        if file_path not in buckets:
            buckets[file_path] = {
                "file": file_path,
                "endpoints": 0,
                "http_clients": 0,
                "grpc_clients": 0,
                "queue_clients": 0,
                "database_clients": 0,
                "cache_clients": 0,
                "storage_clients": 0,
                "security": 0,
                "total": 0,
            }
        buckets[file_path][key] += 1
        buckets[file_path]["total"] += 1

    for item in endpoints:
        add(item, "endpoints")
    for item in http_clients:
        add(item, "http_clients")
    for item in grpc_clients:
        add(item, "grpc_clients")
    for item in queue_clients:
        add(item, "queue_clients")
    for item in database_clients:
        add(item, "database_clients")
    for item in cache_clients:
        add(item, "cache_clients")
    for item in storage_clients:
        add(item, "storage_clients")
    for item in security:
        add(item, "security")

    return sorted(buckets.values(), key=lambda item: item["total"], reverse=True)[:limit]


def _service_inventory(configuration: Dict[str, Any], max_items: int) -> Dict[str, Any]:
    docker_compose = configuration.get("docker_compose", {})
    compose_services = docker_compose.get("services", [])
    compose_names = sorted({service.get("name") for service in compose_services if service.get("name")})
    compose_files = sorted({service.get("file") for service in compose_services if service.get("file")})
    compose_images = sorted({service.get("image") for service in compose_services if service.get("image")})

    k8s = configuration.get("kubernetes", {})
    deployments = k8s.get("deployments", [])
    k8s_services = k8s.get("services", [])
    ingresses = k8s.get("ingresses", [])
    configmaps = k8s.get("configmaps", [])

    return {
        "docker_compose": {
            "files": compose_files[:max_items],
            "service_count": len(compose_names),
            "service_names": compose_names[:max_items],
            "images": compose_images[:max_items],
        },
        "kubernetes": {
            "deployment_count": len(deployments),
            "deployments": [d.get("name") for d in deployments][:max_items],
            "service_count": len(k8s_services),
            "services": [s.get("name") for s in k8s_services][:max_items],
            "ingress_count": len(ingresses),
            "configmap_count": len(configmaps),
        },
    }

@tool
def run_static_analysis(root_path: str, max_items: int = 200) -> Dict[str, Any]:
    """Run static analysis tools on a codebase and return signals.

    Executes static analysis to gather metrics about code structure,
    coverage, hotspots, dependencies, and other signals that inform
    optimization priorities.

    Args:
        root_path: Path to the repository or code directory
        max_items: Maximum number of items to include in results (default: 200)

    Returns:
        JSON string containing static analysis results with signals for:
        - coverage metrics
        - file hotspots
        - dependency ecosystem
        - candidate files for optimization
    """

    start_time = time.time()
    root = Path(root_path).resolve()

    tool_status: Dict[str, Any] = {}
    errors: List[str] = []

    inventory = build_inventory(root)

    endpoints: List[Dict[str, Any]] = []
    http_clients: List[Dict[str, Any]] = []
    grpc_clients: List[Dict[str, Any]] = []
    queue_clients: List[Dict[str, Any]] = []
    database_clients: List[Dict[str, Any]] = []
    cache_clients: List[Dict[str, Any]] = []
    storage_clients: List[Dict[str, Any]] = []
    security_findings: List[Dict[str, Any]] = []

    dependencies: Dict[str, List[Dict[str, Any]]] = {}
    code_structure: Dict[str, Any] = {
        "classes": [],
        "interfaces": [],
        "functions": [],
        "metrics": {},
    }

    configuration: Dict[str, Any] = {}

    # Config analyzer
    try:
        configuration = ConfigAnalyzer(root).analyze()
        tool_status["config_analyzer"] = "ok"
    except Exception as exc:
        tool_status["config_analyzer"] = "error"
        errors.append(f"config_analyzer: {exc}")

    py_results: Dict[str, Any] = {}
    # Python analyzer
    try:
        py_analyzer = PythonAnalyzer(root)
        if py_analyzer.python_files:
            py_results = py_analyzer.analyze()
            _merge_list(http_clients, py_results.get("http_clients", []))
            _merge_list(grpc_clients, py_results.get("grpc_clients", []))
            _merge_list(queue_clients, py_results.get("queue_clients", []))
            _merge_list(database_clients, py_results.get("database_clients", []))
            _merge_list(cache_clients, py_results.get("cache_clients", []))
            _merge_list(storage_clients, py_results.get("storage_clients", []))
            _merge_list(endpoints, py_results.get("endpoints", []))

            dependencies["python"] = py_results.get("dependencies", {}).get("packages", [])
            tool_status["python_analyzer"] = "ok"
        else:
            tool_status["python_analyzer"] = "skipped"
    except Exception as exc:
        tool_status["python_analyzer"] = "error"
        errors.append(f"python_analyzer: {exc}")

    # Semgrep analyzer
    try:
        semgrep = SemgrepAnalyzer(root)
        semgrep_results = semgrep.analyze()
        tool_status["semgrep"] = "ok" if semgrep_results.get("available") else "missing"
        _merge_list(security_findings, semgrep_results.get("security_findings", []))
        _merge_list(endpoints, semgrep_results.get("endpoints", []))
        _merge_list(http_clients, semgrep_results.get("http_clients", []))
        _merge_list(database_clients, semgrep_results.get("database_clients", []))
        _merge_list(cache_clients, semgrep_results.get("cache_clients", []))
        _merge_list(queue_clients, semgrep_results.get("queue_clients", []))
        _merge_list(grpc_clients, semgrep_results.get("grpc_clients", []))
    except Exception as exc:
        tool_status["semgrep"] = "error"
        errors.append(f"semgrep: {exc}")

    # Noir analyzer
    try:
        noir = NoirAnalyzer(root)
        noir_results = noir.analyze()
        tool_status["noir"] = "ok" if noir_results.get("available") else "missing"
        _merge_list(endpoints, noir_results.get("endpoints", []))
    except Exception as exc:
        tool_status["noir"] = "error"
        errors.append(f"noir: {exc}")

    # Tree-sitter analyzer
    try:
        treesitter = TreeSitterAnalyzer(root)
        ts_results = treesitter.analyze()
        tool_status["treesitter"] = "ok" if ts_results.get("available") else "missing"
        _merge_list(code_structure["classes"], ts_results.get("classes", []))
        _merge_list(code_structure["interfaces"], ts_results.get("interfaces", []))
        _merge_list(code_structure["functions"], ts_results.get("functions", []))
        code_structure["metrics"] = ts_results.get("metrics", {})
    except Exception as exc:
        tool_status["treesitter"] = "error"
        errors.append(f"treesitter: {exc}")

    # Native dependency analyzer
    try:
        native_deps = NativeDependencyAnalyzer(root)
        native_results = native_deps.analyze()
        tool_status["native_deps"] = "ok"
        for ecosystem, deps in native_results.get("dependencies", {}).items():
            dependencies.setdefault(ecosystem, [])
            dependencies[ecosystem].extend(deps)
    except Exception as exc:
        tool_status["native_deps"] = "error"
        errors.append(f"native_deps: {exc}")

    # Dedupe and limit lists
    endpoints = dedupe_items(endpoints, ["file", "line", "route", "method", "url", "framework", "source"])
    http_clients = dedupe_items(http_clients, ["file", "line", "library", "method", "url_hint", "source"])
    grpc_clients = dedupe_items(grpc_clients, ["file", "line", "stub_name", "source"])
    queue_clients = dedupe_items(queue_clients, ["file", "line", "queue_type", "role", "source"])
    database_clients = dedupe_items(database_clients, ["file", "line", "library", "type", "source"])
    cache_clients = dedupe_items(cache_clients, ["file", "line", "type", "source"])
    storage_clients = dedupe_items(storage_clients, ["file", "line", "type", "source"])
    security_findings = dedupe_items(security_findings, ["file", "line", "rule_id", "severity", "source"])

    endpoints_limited, endpoints_total = limit_items(endpoints, max_items)
    http_limited, http_total = limit_items(http_clients, max_items)
    grpc_limited, grpc_total = limit_items(grpc_clients, max_items)
    queue_limited, queue_total = limit_items(queue_clients, max_items)
    db_limited, db_total = limit_items(database_clients, max_items)
    cache_limited, cache_total = limit_items(cache_clients, max_items)
    storage_limited, storage_total = limit_items(storage_clients, max_items)
    security_limited, security_total = limit_items(security_findings, max_items)

    # Limit code structure for LLM consumption
    classes_limited, classes_total = limit_items(code_structure.get("classes", []), max_items)
    interfaces_limited, interfaces_total = limit_items(code_structure.get("interfaces", []), max_items)
    functions_limited, functions_total = limit_items(code_structure.get("functions", []), max_items)
    code_structure = {
        "metrics": code_structure.get("metrics", {}),
        "totals": {
            "classes": classes_total,
            "interfaces": interfaces_total,
            "functions": functions_total,
        },
    }

    dependencies_limited: Dict[str, List[Dict[str, Any]]] = {}
    dependencies_totals: Dict[str, int] = {}
    for ecosystem, items in dependencies.items():
        limited, total = limit_items(items, max_items)
        dependencies_limited[ecosystem] = limited
        dependencies_totals[ecosystem] = total

    hotspots = _file_hotspots(
        endpoints=endpoints,
        http_clients=http_clients,
        grpc_clients=grpc_clients,
        queue_clients=queue_clients,
        database_clients=database_clients,
        cache_clients=cache_clients,
        storage_clients=storage_clients,
        security=security_findings,
        limit=min(50, max_items),
    )

    db_types = _count_by(database_clients, "type")
    cache_types = _count_by(cache_clients, "type")
    queue_types = _count_by(queue_clients, "queue_type")

    missing_tools = [tool for tool, status in tool_status.items() if status in {"missing", "error"}]
    total_files = sum(inventory.get("file_extensions", {}).values())

    limits = {
        "max_items": max_items,
        "truncated": {
            "endpoints": max(0, endpoints_total - len(endpoints_limited)),
            "http_clients": max(0, http_total - len(http_limited)),
            "grpc_clients": max(0, grpc_total - len(grpc_limited)),
            "queue_clients": max(0, queue_total - len(queue_limited)),
            "database_clients": max(0, db_total - len(db_limited)),
            "cache_clients": max(0, cache_total - len(cache_limited)),
            "storage_clients": max(0, storage_total - len(storage_limited)),
            "security": max(0, security_total - len(security_limited)),
            "code_classes": max(0, classes_total - len(classes_limited)),
            "code_interfaces": max(0, interfaces_total - len(interfaces_limited)),
            "code_functions": max(0, functions_total - len(functions_limited)),
        },
    }

    result = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "root_path": str(root),
            "elapsed_seconds": round(time.time() - start_time, 2),
            "max_items": max_items,
            "tool_versions": _tool_versions(),
            "schema_version": "1.0",
        },
        "repository": {
            "top_level_directories": inventory.get("top_level_directories", []),
            "language_counts": inventory.get("language_counts", {}),
        },
        "coverage": {
            "total_files": total_files,
            "python_files_analyzed": py_results.get("files_analyzed", 0),
            "treesitter_files_analyzed": code_structure.get("metrics", {}).get("total_files", 0),
            "languages_detected": list(inventory.get("language_counts", {}).keys()),
        },
        "services": _service_inventory(configuration, max_items),
        "dependencies": {
            "summary": dependencies_totals,
            "samples": dependencies_limited,
        },
        "languages": {
            "python": {
                "files_analyzed": py_results.get("files_analyzed", 0),
                "type_analysis": py_results.get("type_analysis", {}),
            }
        },
        "code_structure": code_structure,
        "security": {
            "total": security_total,
            "by_severity": _count_by(security_findings, "severity"),
            "by_category": _count_by(security_findings, "category"),
            "findings": security_limited,
        },
        "endpoints": {
            "total": endpoints_total,
            "items": endpoints_limited,
        },
        "clients": {
            "http": {
                "total": http_total,
                "items": http_limited,
            },
            "grpc": {
                "total": grpc_total,
                "items": grpc_limited,
            },
            "queue": {
                "total": queue_total,
                "types": queue_types,
                "items": queue_limited,
            },
            "database": {
                "total": db_total,
                "types": db_types,
                "items": db_limited,
            },
            "cache": {
                "total": cache_total,
                "types": cache_types,
                "items": cache_limited,
            },
            "storage": {
                "total": storage_total,
                "items": storage_limited,
            },
        },
        "hotspots": hotspots,
        "limits": limits,
        "tools": {
            "status": tool_status,
            "missing": missing_tools,
            "errors": errors,
        },
    }

    return result


def run_static_analysis_json(root_path: str, max_items: int = 200) -> str:
    """Return static analysis results as JSON string."""
    return json.dumps(run_static_analysis(root_path, max_items=max_items), indent=2)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run static analysis tools and output JSON")
    parser.add_argument("path", help="Path to repository")
    parser.add_argument("--max-items", type=int, default=200, help="Max items per list")
    parser.add_argument("--output", help="Write JSON to file")
    args = parser.parse_args()

    result = run_static_analysis(args.path, max_items=args.max_items)
    output = json.dumps(result, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
