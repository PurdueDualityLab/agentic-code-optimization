"""Shared helpers for static analysis tools."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".idea",
    ".vscode",
}

LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".cs": "csharp",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "cpp",
    ".hpp": "cpp",
    ".rs": "rust",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".scala": "scala",
    ".lua": "lua",
    ".sh": "shell",
}


def iter_files(root_path: Path, ignore_dirs: Iterable[str] | None = None) -> Iterable[Path]:
    """Yield files under root_path, skipping ignored dirs."""
    ignore = set(ignore_dirs or DEFAULT_IGNORE_DIRS)
    for current, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in ignore]
        for name in files:
            yield Path(current) / name


def build_inventory(root_path: Path) -> Dict[str, Any]:
    """Collect language and extension inventory for a repo."""
    ext_counts: Dict[str, int] = {}
    lang_counts: Dict[str, int] = {}

    for path in iter_files(root_path):
        ext = path.suffix.lower() or "no_extension"
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
        lang = LANGUAGE_EXTENSIONS.get(path.suffix.lower())
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

    top_dirs = sorted(
        p.name for p in root_path.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )

    return {
        "root": str(root_path),
        "top_level_directories": top_dirs,
        "file_extensions": dict(sorted(ext_counts.items())),
        "language_counts": dict(sorted(lang_counts.items())),
    }


def limit_items(items: List[Dict[str, Any]], limit: int) -> Tuple[List[Dict[str, Any]], int]:
    """Return a limited list and total count."""
    total = len(items)
    if limit <= 0 or total <= limit:
        return items, total
    return items[:limit], total


def dedupe_items(items: List[Dict[str, Any]], keys: List[str]) -> List[Dict[str, Any]]:
    """Dedupe list of dicts using selected keys."""
    seen = set()
    deduped = []
    for item in items:
        token = tuple(item.get(k) for k in keys)
        if token in seen:
            continue
        seen.add(token)
        deduped.append(item)
    return deduped


def safe_run(cmd: List[str], timeout: int, cwd: Path | None = None) -> Tuple[int, str, str]:
    """Run a subprocess command safely."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", "command not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def which(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    return shutil.which(cmd) is not None


def normalize_path(path: str | Path, root: Path) -> str:
    """Return a path relative to root if possible."""
    try:
        return str(Path(path).resolve().relative_to(root))
    except Exception:
        return str(path)
