"""Base classes for static analyzers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class StaticAnalyzer(ABC):
    """Base class for all static analyzers."""

    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path).resolve()
        self.results: Dict[str, Any] = {}

    @abstractmethod
    def analyze(self) -> Dict[str, Any]:
        """Run the static analysis and return structured results."""
        raise NotImplementedError

    def get_results(self) -> Dict[str, Any]:
        """Get cached results."""
        return self.results


class LanguageAnalyzer(StaticAnalyzer):
    """Base class for language-specific analyzers."""

    @abstractmethod
    def extract_call_graph(self) -> Dict[str, Any]:
        """Extract function/method call relationships."""
        raise NotImplementedError

    @abstractmethod
    def extract_imports(self) -> List[Dict[str, Any]]:
        """Extract import/dependency relationships between files."""
        raise NotImplementedError

    @abstractmethod
    def detect_http_clients(self) -> List[Dict[str, Any]]:
        """Detect HTTP client usage for service-to-service calls."""
        raise NotImplementedError

    @abstractmethod
    def detect_database_clients(self) -> List[Dict[str, Any]]:
        """Detect database client usage."""
        raise NotImplementedError
