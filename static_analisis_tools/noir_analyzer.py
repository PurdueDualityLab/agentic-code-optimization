"""OWASP Noir endpoint detection wrapper."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .utils import normalize_path, safe_run, which


class NoirAnalyzer:
    """Wrapper for OWASP Noir endpoint detection."""

    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path).resolve()
        self.available = which("noir")

    def analyze(self) -> Dict[str, Any]:
        if not self.available:
            return {
                "tool": "owasp-noir",
                "available": False,
                "error": "noir not installed",
                "endpoints": [],
            }

        endpoints = self._detect_endpoints()
        return {
            "tool": "owasp-noir",
            "available": True,
            "endpoints": endpoints,
            "total_endpoints": len(endpoints),
        }

    def _detect_endpoints(self) -> List[Dict[str, Any]]:
        code, stdout, stderr = safe_run(
            [
                "noir",
                "-b", str(self.root_path),
                "-f", "json",
                "--no-log",
                "--no-color",
            ],
            timeout=180,
            cwd=self.root_path,
        )

        if code != 0:
            return []

        try:
            noir_data = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            return []

        return self._parse_noir_output(noir_data)

    def _parse_noir_output(self, noir_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        endpoints = []
        for endpoint in noir_data.get("endpoints", []):
            parsed = {
                "method": endpoint.get("method", "UNKNOWN"),
                "url": endpoint.get("url", ""),
                "file": normalize_path(endpoint.get("file", ""), self.root_path),
                "line": endpoint.get("line", 0),
                "params": endpoint.get("params", []),
                "headers": endpoint.get("headers", []),
                "cookies": endpoint.get("cookies", []),
                "protocol": endpoint.get("protocol", "HTTP"),
                "source": "noir",
            }
            endpoints.append(parsed)
        return endpoints
