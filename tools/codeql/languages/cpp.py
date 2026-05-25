"""C++ language adapter.

C++ doesn't have packages, so the per-benchmark scope placeholder is a
*directory prefix* (e.g. `socialNetwork/src/%`) applied to
`File.getRelativePath()`.
"""

from __future__ import annotations

import re

from tools.codeql.fingerprint import BenchmarkFingerprint
from tools.codeql.languages.base import LanguageAdapter


def _cpp_params(fingerprint: BenchmarkFingerprint) -> dict[str, str]:
    src_root = fingerprint.package_filters.get("cpp", "")
    # Build a directory like-pattern. If the fingerprint gave us a root,
    # match anything below it. Otherwise match every file (will cause
    # noisy results but is recoverable — the caller is warned via notes).
    if src_root:
        like = f"{src_root}/%"
        # Capture the next path component as the "service" name.
        escaped = re.escape(src_root).replace("/", "\\\\/")
        # In CodeQL string regex, `\\/` is a literal slash. The result we want is:
        # `<src_root>/([^/]+)/.*`
        regex_capture = f"{src_root}/([^/]+)/.*"
    else:
        like = "%"
        regex_capture = "([^/]+)/.*"

    return {
        "PATH_LIKE": like,
        "PATH_PREFIX": src_root,
        "PATH_REGEX_CAPTURE": regex_capture,
        "RULE_PREFIX": _safe_id(src_root or "anycpp"),
    }


def _safe_id(prefix: str) -> str:
    s = prefix.lower().replace("/", "-").replace(".", "-")
    s = re.sub(r"[^a-z0-9\-]", "", s)
    return s or "cpp"


CPP_ADAPTER = LanguageAdapter(
    language="cpp",
    codeql_language="cpp",
    qlpack_dependencies=("codeql/cpp-all",),
    param_extractor=_cpp_params,
)
