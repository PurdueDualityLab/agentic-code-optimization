"""Python language adapter.

Python's CodeQL library identifies code by *file path* (no formal package
notion at the QL level — modules are just files). The placeholder is the
top-level module directory.
"""

from __future__ import annotations

import re

from tools.codeql.fingerprint import BenchmarkFingerprint
from tools.codeql.languages.base import LanguageAdapter


def _python_params(fingerprint: BenchmarkFingerprint) -> dict[str, str]:
    root = fingerprint.package_filters.get("python", "")
    if root:
        like = f"{root}/%"
        regex_capture = f"{root}/([^/]+).*"
    else:
        like = "%.py"
        regex_capture = "([^/]+).*"

    return {
        "PATH_LIKE": like,
        "MODULE_PREFIX": root,
        "PATH_REGEX_CAPTURE": regex_capture,
        "RULE_PREFIX": _safe_id(root or "anypy"),
    }


def _safe_id(prefix: str) -> str:
    s = prefix.lower().replace("/", "-").replace(".", "-")
    s = re.sub(r"[^a-z0-9\-]", "", s)
    return s or "python"


PYTHON_ADAPTER = LanguageAdapter(
    language="python",
    codeql_language="python",
    qlpack_dependencies=("codeql/python-all",),
    param_extractor=_python_params,
)
