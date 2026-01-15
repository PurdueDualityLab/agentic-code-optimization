"""Tools for the OptimizerAgent to safely apply code changes."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from tools.analysis import read_code_snippet


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


def _normalize_allowed_paths(paths: List[str], root_path: str) -> set[str]:
    normalized: set[str] = set()
    root = Path(root_path).resolve() if root_path else None
    root_name = root.name if root else ""

    for raw in paths:
        if not raw:
            continue
        raw_norm = raw.replace("\\", "/")
        path_obj = Path(raw_norm)
        if path_obj.is_absolute():
            if root:
                try:
                    normalized.add(path_obj.resolve().relative_to(root).as_posix())
                    continue
                except Exception:
                    pass
        if root_name and raw_norm.startswith(f"{root_name}/"):
            raw_norm = raw_norm[len(root_name) + 1 :]
        normalized.add(raw_norm)
    return normalized


def _allowed_files_from_analysis(analysis: Dict[str, Any], root_path: str) -> List[str]:
    priorities = analysis.get("priorities", [])
    suggested = analysis.get("suggested_focus_files", [])

    suggested_files = [
        item.get("file") for item in suggested if isinstance(item, dict) and item.get("file")
    ]

    evidence_files = []
    for item in priorities:
        if not isinstance(item, dict):
            continue
        evidence_file = item.get("evidence_file")
        evidence_lines = item.get("evidence_lines")
        needs_inspection = item.get("needs_inspection")
        if evidence_file and evidence_lines and not needs_inspection:
            evidence_files.append(evidence_file)

    suggested_set = _normalize_allowed_paths(suggested_files, root_path)
    evidence_set = _normalize_allowed_paths(evidence_files, root_path)

    if evidence_set:
        if suggested_set:
            intersection = evidence_set & suggested_set
            allowed = intersection if intersection else evidence_set
        else:
            allowed = evidence_set
    else:
        allowed = suggested_set

    return sorted(allowed)


@tool
def load_analysis_report(analysis_source: str) -> str:
    """Load analysis JSON from a path or raw JSON string."""
    try:
        data = _read_json(analysis_source)
    except Exception:
        return _read_text(analysis_source)
    return json.dumps(data)


@tool
def load_summary_text(summary_source: str) -> str:
    """Load summary text from a path or raw text."""
    return _read_text(summary_source)


def _preview_snippet_patch_impl(
    file_path: str,
    old_snippet: str,
    new_snippet: str,
    root_path: str = "",
    allowed_files: Optional[List[str]] = None,
) -> str:
    """Preview a safe snippet replacement without writing."""
    if not old_snippet:
        return json.dumps({"error": "empty_old_snippet"})

    path = _resolve_path(file_path, root_path)
    if not path or not path.exists() or not path.is_file():
        return json.dumps({"error": "file_not_found", "file": file_path})

    if allowed_files:
        allowed = {p.replace("\\", "/") for p in allowed_files}
        rel = _normalize_relative(path, root_path)
        if rel not in allowed:
            return json.dumps({"error": "file_not_allowed", "file": rel})

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
def preview_snippet_patch(
    file_path: str,
    old_snippet: str,
    new_snippet: str,
    root_path: str = "",
    allowed_files: Optional[List[str]] = None,
) -> str:
    """Preview a safe snippet replacement without writing."""
    return _preview_snippet_patch_impl(
        file_path=file_path,
        old_snippet=old_snippet,
        new_snippet=new_snippet,
        root_path=root_path,
        allowed_files=allowed_files,
    )

def _apply_snippet_patch_impl(
    file_path: str,
    old_snippet: str,
    new_snippet: str,
    root_path: str = "",
    allowed_files: Optional[List[str]] = None,
) -> str:
    """Apply a safe snippet replacement in a file."""
    if not old_snippet:
        return json.dumps({"error": "empty_old_snippet"})

    path = _resolve_path(file_path, root_path)
    if not path or not path.exists() or not path.is_file():
        return json.dumps({"error": "file_not_found", "file": file_path})

    if allowed_files:
        allowed = {p.replace("\\", "/") for p in allowed_files}
        rel = _normalize_relative(path, root_path)
        if rel not in allowed:
            return json.dumps({"error": "file_not_allowed", "file": rel})

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
def apply_snippet_patch(
    file_path: str,
    old_snippet: str,
    new_snippet: str,
    root_path: str = "",
    allowed_files: Optional[List[str]] = None,
) -> str:
    """Apply a safe snippet replacement in a file."""
    return _apply_snippet_patch_impl(
        file_path=file_path,
        old_snippet=old_snippet,
        new_snippet=new_snippet,
        root_path=root_path,
        allowed_files=allowed_files,
    )


@tool
def preview_snippet_patch_guarded(
    file_path: str,
    old_snippet: str,
    new_snippet: str,
    root_path: str,
    analysis_source: str,
) -> str:
    """Preview a snippet replacement, constrained by analysis report."""
    analysis = _read_json(analysis_source)
    allowed_files = _allowed_files_from_analysis(analysis, root_path)
    if not allowed_files:
        return json.dumps({"error": "no_allowed_files"})
    return _preview_snippet_patch_impl(
        file_path=file_path,
        old_snippet=old_snippet,
        new_snippet=new_snippet,
        root_path=root_path,
        allowed_files=allowed_files,
    )


@tool
def apply_snippet_patch_guarded(
    file_path: str,
    old_snippet: str,
    new_snippet: str,
    root_path: str,
    analysis_source: str,
) -> str:
    """Apply a snippet replacement, constrained by analysis report."""
    analysis = _read_json(analysis_source)
    allowed_files = _allowed_files_from_analysis(analysis, root_path)
    if not allowed_files:
        return json.dumps({"error": "no_allowed_files"})
    return _apply_snippet_patch_impl(
        file_path=file_path,
        old_snippet=old_snippet,
        new_snippet=new_snippet,
        root_path=root_path,
        allowed_files=allowed_files,
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
