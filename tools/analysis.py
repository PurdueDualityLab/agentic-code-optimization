"""Tools for the AnalyzerAgent to load and compress inputs."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool


MAX_SNIPPET_LINES = 400
MAX_SNIPPET_CHARS = 8000


def _read_text(source: str) -> str:
    path = Path(source)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    return source


def _read_json(source: str) -> Dict[str, Any]:
    path = Path(source)
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="ignore")
    else:
        text = source
    return json.loads(text)


def _parse_summary_sections(text: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for line in text.splitlines():
        match = re.match(r"^\s*\d+\)\s+(.+)$", line)
        if match:
            current = match.group(1).strip()
            sections[current] = []
            continue
        if current is not None and line.strip():
            sections[current].append(line.strip())
    return sections


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except Exception:
        return path.as_posix()


def _add_signal(signals: List[Dict[str, Any]], signal_id: str, severity: str, message: str, evidence: Dict[str, Any]) -> None:
    signals.append({
        "id": signal_id,
        "severity": severity,
        "message": message,
        "evidence": evidence,
    })


def _is_test_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if (
        "/test/" in normalized
        or "/tests/" in normalized
        or "/testing/" in normalized
        or "/spec/" in normalized
        or "/specs/" in normalized
    ):
        return True
    if normalized.endswith(("/test", "/tests", "/testing", "/spec", "/specs")):
        return True

    name = normalized.rsplit("/", 1)[-1]
    if name.startswith("test"):
        return True
    if name.startswith("spec"):
        return True
    if name in {"test.py", "tests.py", "testing.py", "spec.py", "specs.py"}:
        return True
    if name.endswith(("_test.py", "_test.go", "_test.cc", "_test.cpp", "_test.c", "_spec.py", "_spec.ts", "_spec.js")):
        return True
    return False


def _candidate_files(
    hotspots: List[Dict[str, Any]],
    clients: Dict[str, Any],
    security_findings: List[Dict[str, Any]],
    limit: int,
    exclude_tests: bool = True,
) -> List[str]:
    files: List[str] = []

    for item in hotspots:
        file_path = item.get("file")
        if file_path:
            files.append(file_path)

    for finding in security_findings:
        file_path = finding.get("file")
        if file_path:
            files.append(file_path)

    for client_data in clients.values():
        for item in client_data.get("items", [])[:limit]:
            file_path = item.get("file")
            if file_path:
                files.append(file_path)

    if exclude_tests:
        filtered = [path for path in files if not _is_test_path(path)]
        if filtered:
            files = filtered

    deduped = []
    seen = set()
    for file_path in files:
        if file_path in seen:
            continue
        seen.add(file_path)
        deduped.append(file_path)
        if len(deduped) >= limit:
            break

    return deduped


@tool
def load_environment_summary(summary_source: str) -> str:
    """Load environment/component/behavior summary text from path or raw text."""
    return _read_text(summary_source)


@tool
def load_static_analysis(static_source: str) -> str:
    """Load static analysis JSON from path or raw JSON string."""
    data = _read_json(static_source)
    return json.dumps(data)


@tool
def read_code_snippet(
    file_path: str,
    root_path: str = "",
    start_line: int = 1,
    max_lines: int = 200,
    max_chars: int = 4000,
) -> str:
    """Read a bounded snippet from a file. Returns JSON with snippet and metadata."""
    max_lines = max(1, min(max_lines, MAX_SNIPPET_LINES))
    max_chars = max(200, min(max_chars, MAX_SNIPPET_CHARS))
    start_line = max(1, start_line)

    path = Path(file_path)
    if not path.is_absolute() and root_path:
        path = Path(root_path) / file_path

    try:
        path = path.resolve()
    except Exception:
        return json.dumps({"error": "invalid_path", "file": file_path})

    if root_path:
        root = Path(root_path).resolve()
        if root not in path.parents and path != root:
            return json.dumps({"error": "path_outside_root", "file": str(path)})

    if not path.exists() or not path.is_file():
        return json.dumps({"error": "file_not_found", "file": str(path)})

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    total_lines = len(lines)

    start_index = start_line - 1
    end_index = min(start_index + max_lines, total_lines)
    snippet_lines = lines[start_index:end_index]

    snippet = "\n".join(snippet_lines)
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars]

    payload = {
        "file": str(path),
        "start_line": start_line,
        "end_line": end_index,
        "total_lines": total_lines,
        "snippet": snippet,
    }
    return json.dumps(payload)


@tool
def search_codebase(
    pattern: str,
    root_path: str = "",
    file_glob: str = "",
    max_results: int = 50,
    ignore_case: bool = True,
    literal: bool = True,
) -> str:
    """Search for a pattern in the codebase. Returns JSON with match locations."""
    if not pattern:
        return json.dumps({"error": "empty_pattern"})

    root = Path(root_path).resolve() if root_path else Path.cwd().resolve()
    if not root.exists():
        return json.dumps({"error": "root_not_found", "root_path": str(root)})

    max_results = max(1, min(max_results, 200))
    results: List[Dict[str, Any]] = []
    truncated = False

    if shutil.which("rg"):
        cmd = ["rg", "--no-heading", "--line-number", "--color", "never"]
        if ignore_case:
            cmd.append("-i")
        if literal:
            cmd.append("-F")
        if file_glob:
            cmd.extend(["-g", file_glob])
        cmd.append(pattern)
        cmd.append(str(root))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(root),
                timeout=30,
            )
        except Exception as exc:
            return json.dumps({"error": "rg_failed", "detail": str(exc)})

        if proc.returncode not in (0, 1):
            return json.dumps({"error": "rg_failed", "detail": proc.stderr.strip()})

        for line in proc.stdout.splitlines():
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            path_str, line_str, text = parts[0], parts[1], parts[2]
            try:
                line_no = int(line_str)
            except ValueError:
                continue
            match_path = (root / path_str).resolve() if not Path(path_str).is_absolute() else Path(path_str)
            results.append({
                "file": _relative_path(match_path, root),
                "line": line_no,
                "text": text[:200],
            })
            if len(results) >= max_results:
                truncated = True
                break
    else:
        flags = re.IGNORECASE if ignore_case else 0
        regex_pattern = re.escape(pattern) if literal else pattern
        try:
            regex = re.compile(regex_pattern, flags=flags)
        except re.error as exc:
            return json.dumps({"error": "invalid_regex", "detail": str(exc)})
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if file_glob and not path.match(file_glob):
                continue
            try:
                if path.stat().st_size > 1_000_000:
                    continue
            except OSError:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for idx, line in enumerate(content.splitlines(), start=1):
                if regex.search(line):
                    results.append({
                        "file": _relative_path(path, root),
                        "line": idx,
                        "text": line[:200],
                    })
                    if len(results) >= max_results:
                        truncated = True
                        break
            if truncated:
                break

    payload = {
        "pattern": pattern,
        "root_path": str(root),
        "file_glob": file_glob or None,
        "results": results,
        "truncated": truncated,
    }
    return json.dumps(payload)


@tool
def build_analysis_bundle(
    summary_source: str,
    static_source: str,
    max_items: int = 12,
    max_excerpt_chars: int = 0,
) -> str:
    """Build a compact analysis bundle from summary text and static analysis JSON."""
    summary_text = _read_text(summary_source)
    static_data = _read_json(static_source)

    sections = _parse_summary_sections(summary_text)
    summary_focus = {
        key: sections.get(key, [])
        for key in [
            "Project Type",
            "Primary Languages",
            "Frameworks & Libraries (key)",
            "Containerization",
            "Deployment",
            "CI/CD",
            "Special Features and Notes",
        ]
        if key in sections
    }

    metadata = static_data.get("metadata", {})
    repository = static_data.get("repository", {})
    if repository and "language_counts" in repository:
        repository = dict(repository)
        repository["language_counts_unit"] = "files"
    coverage = static_data.get("coverage", {})
    services = static_data.get("services", {})
    dependencies = static_data.get("dependencies", {})
    clients = static_data.get("clients", {})
    security = static_data.get("security", {})
    endpoints = static_data.get("endpoints", {})
    hotspots = static_data.get("hotspots", [])[:max_items]
    tools = static_data.get("tools", {})

    client_totals = {name: data.get("total", 0) for name, data in clients.items()}
    client_types = {name: data.get("types", {}) for name, data in clients.items() if data.get("types")}
    client_samples = {name: data.get("items", [])[:max_items] for name, data in clients.items() if data.get("items")}

    security_findings = security.get("findings", [])[:max_items]

    signals: List[Dict[str, Any]] = []
    missing_tools = tools.get("missing", [])
    if missing_tools:
        _add_signal(
            signals,
            "missing_tools",
            "high",
            "Static analysis coverage is incomplete due to missing tools.",
            {"missing": missing_tools},
        )

    total_files = coverage.get("total_files", 0)
    py_analyzed = coverage.get("python_files_analyzed", 0)
    if total_files and py_analyzed:
        ratio = py_analyzed / max(total_files, 1)
        if ratio < 0.05:
            _add_signal(
                signals,
                "low_python_coverage",
                "medium",
                "Only a small fraction of files were analyzed with Python AST tools.",
                {"ratio": round(ratio, 4), "python_files_analyzed": py_analyzed, "total_files": total_files},
            )

    if coverage.get("treesitter_files_analyzed", 0) == 0:
        _add_signal(
            signals,
            "treesitter_missing",
            "medium",
            "Tree-sitter analysis did not run, so structure for non-Python code is missing.",
            {"treesitter_files_analyzed": 0},
        )

    endpoints_total = endpoints.get("total", 0)
    if endpoints_total == 0:
        _add_signal(
            signals,
            "no_endpoints_detected",
            "low",
            "No endpoints detected; verify with runtime or additional static tooling.",
            {"endpoints_total": 0},
        )

    http_total = client_totals.get("http", 0)
    if http_total >= 100:
        _add_signal(
            signals,
            "high_http_client_usage",
            "medium",
            "High volume of HTTP client calls detected; may indicate chatty service mesh.",
            {"http_clients": http_total},
        )

    service_count = services.get("docker_compose", {}).get("service_count", 0)
    if service_count >= 50:
        _add_signal(
            signals,
            "many_services",
            "medium",
            "Large number of services detected; optimization likely needs prioritization.",
            {"service_count": service_count},
        )

    if security.get("total", 0) > 0:
        _add_signal(
            signals,
            "security_findings_present",
            "high",
            "Security findings exist; address before performance optimizations.",
            {"security_total": security.get("total")},
        )

    languages = repository.get("language_counts", {})
    if len(languages.keys()) >= 3:
        _add_signal(
            signals,
            "polyglot_repo",
            "low",
            "Multiple languages detected; optimization must consider language-specific tooling.",
            {"languages": list(languages.keys())},
        )

    candidates = _candidate_files(hotspots, clients, security_findings, max_items)

    if hotspots:
        test_hotspots = [item for item in hotspots if _is_test_path(item.get("file", ""))]
        ratio = len(test_hotspots) / max(len(hotspots), 1)
        if ratio >= 0.6:
            _add_signal(
                signals,
                "hotspots_are_tests",
                "medium",
                "Most hotspots are in test files; treat them as lower priority unless validated in production paths.",
                {"test_hotspots": len(test_hotspots), "hotspots_total": len(hotspots)},
            )

    bundle = {
        "summary_sections": summary_focus,
        "static": {
            "metadata": {
                "root_path": metadata.get("root_path"),
                "tool_versions": metadata.get("tool_versions", {}),
            },
            "repository": repository,
            "coverage": coverage,
            "services": services,
            "dependencies_summary": dependencies.get("summary", {}),
            "dependencies_samples": dependencies.get("samples", {}),
            "clients_totals": client_totals,
            "clients_types": client_types,
            "clients_samples": client_samples,
            "security_summary": {
                "total": security.get("total", 0),
                "by_severity": security.get("by_severity", {}),
                "by_category": security.get("by_category", {}),
                "findings": security_findings,
            },
            "endpoints_total": endpoints_total,
            "endpoints_samples": endpoints.get("items", [])[:max_items],
            "hotspots": hotspots,
            "candidate_files": candidates,
        },
        "signals": signals,
        "limits": static_data.get("limits", {}),
        "tools": tools,
    }

    if max_excerpt_chars > 0:
        bundle["summary_excerpt"] = summary_text[:max_excerpt_chars]

    return json.dumps(bundle, indent=2)
