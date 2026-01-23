"""Tools for the OptimizerAgent to safely apply code changes."""

from __future__ import annotations

import asyncio
import difflib
import json
from pathlib import Path
from typing import Any, Dict

from langchain_core.tools import tool

from tools.analysis import read_code_snippet, read_file


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
    if not text or not text.strip():
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _resolve_path(file_path: str, root_path: str) -> Path | None:
    path = Path(file_path)
    if not path.is_absolute() and root_path:
        path = Path(root_path) / file_path
    try:
        path = path.resolve()
    except Exception:
        return None
    if root_path:
        root = Path(root_path).resolve()
        if root not in path.parents and path != root:
            return None
    return path


def _normalize_relative(path: Path, root_path: str) -> str:
    if not root_path:
        return path.as_posix()
    root = Path(root_path).resolve()
    try:
        return path.relative_to(root).as_posix()
    except Exception:
        return path.as_posix()


@tool
async def load_analysis_report(analysis_source: str) -> str:
    """Load analysis JSON from a path or raw JSON string."""
    try:
        data = _read_json(analysis_source)
    except Exception:
        return _read_text(analysis_source)
    return json.dumps(data)


@tool
async def load_summary_text(summary_source: str) -> str:
    """Load summary text from a path or raw text."""
    return _read_text(summary_source)


def _preview_snippet_patch_impl(
    file_path: str,
    old_snippet: str,
    new_snippet: str,
    root_path: str = "",
) -> str:
    """Preview a safe snippet replacement without writing."""
    if not old_snippet:
        return json.dumps({"error": "empty_old_snippet"})

    path = _resolve_path(file_path, root_path)
    if not path or not path.exists() or not path.is_file():
        return json.dumps({"error": "file_not_found", "file": file_path})

    original = path.read_text(encoding="utf-8", errors="ignore")
    count = original.count(old_snippet)
    if count == 0:
        return json.dumps({"error": "snippet_not_found", "file": str(path)})
    if count > 1:
        return json.dumps({"error": "snippet_not_unique", "file": str(path), "count": count})

    updated = original.replace(old_snippet, new_snippet, 1)
    diff = "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile=str(path),
            tofile=str(path),
            lineterm="",
        )
    )

    return json.dumps({
        "file": str(path),
        "applied": False,
        "diff": diff,
    })


@tool
async def preview_snippet_patch(
    file_path: str,
    old_snippet: str,
    new_snippet: str,
    root_path: str = "",
) -> str:
    """Preview a safe snippet replacement without writing."""
    return _preview_snippet_patch_impl(
        file_path=file_path,
        old_snippet=old_snippet,
        new_snippet=new_snippet,
        root_path=root_path,
    )

def _apply_snippet_patch_impl(
    file_path: str,
    old_snippet: str,
    new_snippet: str,
    root_path: str = "",
) -> str:
    """Apply a safe snippet replacement in a file."""
    if not old_snippet:
        return json.dumps({"error": "empty_old_snippet"})

    path = _resolve_path(file_path, root_path)
    if not path or not path.exists() or not path.is_file():
        return json.dumps({"error": "file_not_found", "file": file_path})

    original = path.read_text(encoding="utf-8", errors="ignore")
    count = original.count(old_snippet)
    if count == 0:
        return json.dumps({"error": "snippet_not_found", "file": str(path)})
    if count > 1:
        return json.dumps({"error": "snippet_not_unique", "file": str(path), "count": count})

    updated = original.replace(old_snippet, new_snippet, 1)
    if updated == original:
        return json.dumps({"error": "no_change", "file": str(path)})

    path.write_text(updated, encoding="utf-8")
    diff = "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile=str(path),
            tofile=str(path),
            lineterm="",
        )
    )

    return json.dumps({
        "file": str(path),
        "applied": True,
        "diff": diff,
    })


@tool
async def apply_snippet_patch(
    file_path: str,
    old_snippet: str,
    new_snippet: str,
    root_path: str = "",
) -> str:
    """Apply a safe snippet replacement in a file."""
    return _apply_snippet_patch_impl(
        file_path=file_path,
        old_snippet=old_snippet,
        new_snippet=new_snippet,
        root_path=root_path,
    )


@tool
async def preview_snippet_patch_guarded(
    file_path: str,
    old_snippet: str,
    new_snippet: str,
    root_path: str,
    analysis_source: str,
) -> str:
    """Preview a snippet replacement, constrained by analysis report."""
    return _preview_snippet_patch_impl(
        file_path=file_path,
        old_snippet=old_snippet,
        new_snippet=new_snippet,
        root_path=root_path,
    )


@tool
async def apply_snippet_patch_guarded(
    file_path: str,
    old_snippet: str,
    new_snippet: str,
    root_path: str,
    analysis_source: str,
) -> str:
    """Apply a snippet replacement, constrained by analysis report."""
    return _apply_snippet_patch_impl(
        file_path=file_path,
        old_snippet=old_snippet,
        new_snippet=new_snippet,
        root_path=root_path,
    )


__all__ = [
    "load_analysis_report",
    "load_summary_text",
    "preview_snippet_patch",
    "apply_snippet_patch",
    "preview_snippet_patch_guarded",
    "apply_snippet_patch_guarded",
    "read_code_snippet",
]
