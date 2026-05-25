"""Language adapters: small per-language plugins consumed by the runner.

Each adapter knows: its CodeQL language id, its file extensions, how to
materialise its `package_filter` placeholder, and where its templates live.

Add a new language by dropping a `<lang>.py` file in this directory that
exports a `LanguageAdapter` instance, and registering it in `LANGUAGE_ADAPTERS`
below.
"""

from tools.codeql.languages.base import LanguageAdapter
from tools.codeql.languages.cpp import CPP_ADAPTER
from tools.codeql.languages.java import JAVA_ADAPTER
from tools.codeql.languages.python import PYTHON_ADAPTER

LANGUAGE_ADAPTERS: dict[str, LanguageAdapter] = {
    "java": JAVA_ADAPTER,
    "cpp": CPP_ADAPTER,
    "python": PYTHON_ADAPTER,
}


def get_adapter(language: str) -> LanguageAdapter | None:
    """Look up a registered adapter by language id (returns None if missing)."""
    return LANGUAGE_ADAPTERS.get(language)


__all__ = [
    "LANGUAGE_ADAPTERS",
    "LanguageAdapter",
    "JAVA_ADAPTER",
    "CPP_ADAPTER",
    "PYTHON_ADAPTER",
    "get_adapter",
]
