"""Language adapter abstract base.

Adapters are deliberately minimal — everything language-specific that the
*queries* need (package filter syntax, naming conventions for what counts
as an "endpoint", etc.) lives in the templates themselves, parameterised
by placeholders the adapter computes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from tools.codeql.fingerprint import BenchmarkFingerprint


@dataclass(frozen=True)
class LanguageAdapter:
    """Per-language configuration consumed by the renderer + runner.

    Attributes:
        language: Internal language id (e.g. 'java'). Matches taxonomy keys.
        codeql_language: The id used by `codeql database create --language`
            (usually identical, but kept separate for cases like `c-cpp`).
        qlpack_dependencies: Library dependencies to embed in qlpack.yml.
        param_extractor: Callable that converts a fingerprint into a dict of
            template placeholder values for this language. Concentrating the
            logic here means templates stay free of conditional fingerprint-
            inspection logic.
    """

    language: str
    codeql_language: str
    qlpack_dependencies: tuple[str, ...]
    param_extractor: Callable[[BenchmarkFingerprint], dict[str, str]]

    def extract_params(self, fingerprint: BenchmarkFingerprint) -> dict[str, str]:
        """Build the placeholder dict for this language given a fingerprint."""
        return self.param_extractor(fingerprint)
