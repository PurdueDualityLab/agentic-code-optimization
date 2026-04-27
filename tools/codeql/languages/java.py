"""Java language adapter.

The package filter is the most important placeholder for Java. Every
template uses `${PACKAGE_LIKE}` to scope its `package.getName().matches(...)`
predicate. The capture group `${PACKAGE_REGEX_CAPTURE}` is used for
extracting a per-service slice (e.g. the `auth` part of
`tools.descartes.teastore.auth`).
"""

from __future__ import annotations

import re

from tools.codeql.fingerprint import BenchmarkFingerprint
from tools.codeql.languages.base import LanguageAdapter


def _java_params(fingerprint: BenchmarkFingerprint) -> dict[str, str]:
    pkg_filter = fingerprint.package_filters.get("java", "%")
    # `package_filters` stores the wildcard form ("foo.bar.%"); strip it for
    # the dot-stripped prefix used inside the regexpCapture group.
    if pkg_filter.endswith(".%"):
        prefix = pkg_filter[:-2]
    else:
        prefix = pkg_filter.rstrip(".")
    # Build a CodeQL regex that captures the next component after the prefix.
    # Used by templates that want to attribute findings to a sub-service.
    if prefix:
        # Escape the dots inside the regex: in CodeQL regex strings, `\\.`
        # is literal dot. The `[^.]+` captures the next component.
        escaped_prefix = prefix.replace(".", "\\\\.")
        regex_capture = f"{escaped_prefix}\\\\.([^.]+).*"
    else:
        regex_capture = "([^.]+).*"

    return {
        "PACKAGE_LIKE": pkg_filter or "%",
        "PACKAGE_PREFIX": prefix,
        "PACKAGE_REGEX_CAPTURE": regex_capture,
        "RULE_PREFIX": _safe_id(prefix or "anyjava"),
    }


def _safe_id(prefix: str) -> str:
    """Sanitise a package prefix for use in a CodeQL @id (lowercase, dashes)."""
    s = prefix.lower().replace(".", "-")
    s = re.sub(r"[^a-z0-9\-]", "", s)
    return s or "java"


JAVA_ADAPTER = LanguageAdapter(
    language="java",
    codeql_language="java",
    qlpack_dependencies=("codeql/java-all",),
    param_extractor=_java_params,
)
