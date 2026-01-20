"""Tools for the AnalyzerAgent to load and compress inputs."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
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

@tool
async def read_code_snippet(
    file_path: str,
    root_path: str = "",
    start_line: int = 1,
    max_lines: int = 200,
    max_chars: int = 4000,
) -> str:
    """Read a bounded snippet from a file in the codebase.

    Args:
        file_path (str): **REQUIRED** Path to the file to read (e.g., "src/main.py", "agents/base.py")
        root_path (str): Root directory path. Use this if file_path is relative. Defaults to current directory.
        start_line (int): Line number to start reading from (1-indexed). Default: 1
        max_lines (int): Maximum number of lines to read (1-400). Default: 200
        max_chars (int): Maximum characters to return (200-8000). Default: 4000

    Returns:
        str: JSON string with format: {"file": "absolute/path", "start_line": 1, "end_line": 200, "total_lines": 500, "snippet": "file contents..."}

    Examples:
        # Read first 200 lines of a file
        read_code_snippet(file_path="agents/base.py")

        # Read specific section of a file
        read_code_snippet(file_path="src/main.py", start_line=50, max_lines=100)

        # Read with custom character limit
        read_code_snippet(file_path="config.ini", max_chars=1000)
    """
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
async def read_file(
    file_path: str,
    root_path: str = "",
    start_line: int = 1,
    max_lines: int = 200,
) -> str:
    """Read contents of a file from the codebase.

    This is an alias for read_code_snippet with a more intuitive name.
    Use this when you want to read file contents for analysis or inspection.

    Args:
        file_path (str): **REQUIRED** Path to the file to read (e.g., "src/main.py", "config.ini")
        root_path (str): Root directory path. Use this if file_path is relative. Defaults to current directory.
        start_line (int): Line number to start reading from (1-indexed). Default: 1
        max_lines (int): Maximum number of lines to read. Default: 200

    Returns:
        str: JSON string with format: {"file": "absolute/path", "start_line": 1, "end_line": 200, "total_lines": 500, "snippet": "file contents..."}

    Examples:
        # Read entire file (up to max_lines)
        read_file(file_path="agents/base.py")

        # Read specific section of a file
        read_file(file_path="src/main.py", start_line=50, max_lines=100)

        # Read configuration file
        read_file(file_path="config.ini", root_path="/path/to/project")
    """
    return await read_code_snippet(
        file_path=file_path,
        root_path=root_path,
        start_line=start_line,
        max_lines=max_lines,
    )


@tool
async def search_codebase(
    pattern: str,
    root_path: str = "",
    file_glob: str = "",
    max_results: int = 50,
    ignore_case: bool = True,
    literal: bool = True,
) -> str:
    """Search for a text pattern in the codebase using ripgrep or regex.

    Args:
        pattern (str): **REQUIRED** The text pattern to search for (e.g., "def main", "TODO", "import json")
        root_path (str): Root directory to search in. Defaults to current working directory.
        file_glob (str): File pattern to filter results (e.g., "*.py", "**/*.go"). Leave empty to search all files.
        max_results (int): Maximum number of results to return (1-200). Default: 50
        ignore_case (bool): Whether to ignore case when searching. Default: True
        literal (bool): Treat pattern as literal string (not regex). Default: True

    Returns:
        str: JSON string with format: {"matches": [{"file": "path/to/file.py", "line": 42, "text": "matched line"}], "truncated": bool}

    Examples:
        # Search for function definitions in Python files
        search_codebase(pattern="def process_data", file_glob="*.py")

        # Search for imports across entire codebase
        search_codebase(pattern="import asyncio")

        # Case-sensitive search for a constant
        search_codebase(pattern="MAX_ITERATIONS", ignore_case=False)
    """
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
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(root),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            return json.dumps({"error": "rg_timeout"})
        except Exception as exc:
            return json.dumps({"error": "rg_failed", "detail": str(exc)})

        if proc.returncode not in (0, 1):
            return json.dumps({"error": "rg_failed", "detail": stderr.decode().strip()})

        for line in stdout.decode().splitlines():
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
async def build_analysis_bundle(
    summary_source: str,
    max_items: int = 12,
    max_excerpt_chars: int = 0,
) -> str:
    """Build a compact analysis bundle from environment/component/behavior summaries only.

    This tool merges the summary sections into a compact bundle without incorporating
    separate static analysis findings.

    Args:
        summary_source (str): **REQUIRED** Path to summary file or raw summary text
        max_items (int): Maximum number of summary items per section. Default: 12
        max_excerpt_chars (int): Maximum characters for summary excerpt (0=no excerpt). Default: 0

    Returns:
        str: Compact analysis bundle as formatted JSON text containing summaries only

    Examples:
        # Build bundle with summary only
        build_analysis_bundle(summary_source="/tmp/summary.txt")

        # Build bundle with an excerpt
        build_analysis_bundle(summary_source="/tmp/summary.txt", max_excerpt_chars=500)
    """
    summary_text = _read_text(summary_source)
    sections = _parse_summary_sections(summary_text)
    summary_sections = {
        key: items[:max_items]
        for key, items in sections.items()
    }

    bundle = {
        "summary_text": summary_text,
        "summary_sections": summary_sections,
    }

    if max_excerpt_chars > 0:
        bundle["summary_excerpt"] = summary_text[:max_excerpt_chars]

    return json.dumps(bundle, indent=2)
