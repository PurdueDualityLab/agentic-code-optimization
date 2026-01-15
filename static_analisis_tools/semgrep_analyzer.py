"""Semgrep-based static analysis for multi-language scanning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .utils import normalize_path, safe_run, which


class SemgrepAnalyzer:
    """Run Semgrep and normalize results for downstream analysis."""

    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path).resolve()
        self.available = which("semgrep")
        self.detected_languages = self._detect_languages()

    def analyze(self) -> Dict[str, Any]:
        if not self.available:
            return {
                "tool": "semgrep",
                "available": False,
                "error": "semgrep not installed",
                "languages": self.detected_languages,
                "security_findings": [],
                "endpoints": [],
                "http_clients": [],
                "database_clients": [],
                "cache_clients": [],
                "queue_clients": [],
                "grpc_clients": [],
            }

        raw_results = self._run_semgrep()
        parsed = {
            "tool": "semgrep",
            "available": True,
            "languages": self.detected_languages,
            "security_findings": self._extract_security(raw_results),
            "endpoints": self._extract_endpoints(raw_results),
            "http_clients": self._extract_http_clients(raw_results),
            "database_clients": self._extract_database_clients(raw_results),
            "cache_clients": self._extract_cache_clients(raw_results),
            "queue_clients": self._extract_queue_clients(raw_results),
            "grpc_clients": self._extract_grpc_clients(raw_results),
            "raw_findings": raw_results.get("results", [])[:100],
        }
        return parsed

    def _detect_languages(self) -> List[str]:
        language_extensions = {
            ".py": "python",
            ".cs": "csharp",
            ".java": "java",
            ".kt": "kotlin",
            ".go": "go",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".rb": "ruby",
            ".rs": "rust",
            ".php": "php",
            ".swift": "swift",
            ".c": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".h": "cpp",
            ".hpp": "cpp",
            ".scala": "scala",
        }

        detected = set()
        for ext, lang in language_extensions.items():
            if any(self.root_path.rglob(f"*{ext}")):
                detected.add(lang)
        return sorted(detected)

    def _run_semgrep(self) -> Dict[str, Any]:
        custom_rules_dir = None
        current = self.root_path
        for _ in range(4):
            candidate = current / ".semgrep"
            if candidate.exists():
                custom_rules_dir = candidate
                break
            current = current.parent

        config_arg = str(custom_rules_dir) if custom_rules_dir else "auto"
        cmd = [
            "semgrep",
            f"--config={config_arg}",
            "--json",
            "--quiet",
            "--no-git-ignore",
            "--exclude", "node_modules",
            "--exclude", "target",
            "--exclude", "*.jar",
            "--exclude", "*.class",
            "--exclude", "*.war",
            "--max-target-bytes=1000000",
            str(self.root_path),
        ]

        code, stdout, stderr = safe_run(cmd, timeout=300, cwd=self.root_path)
        if code not in (0, 1):
            return {"error": stderr.strip(), "results": []}

        try:
            return json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            return {"error": "failed to parse semgrep json", "results": []}

    def _extract_security(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        findings = []
        for result in results.get("results", []):
            extra = result.get("extra", {})
            metadata = extra.get("metadata", {})
            severity = extra.get("severity", "INFO")
            if severity.upper() in {"ERROR", "WARNING", "INFO"}:
                cwe = metadata.get("cwe") or metadata.get("cwe_id")
                owasp = metadata.get("owasp")
                confidence = metadata.get("confidence") or extra.get("confidence")
                impact = metadata.get("impact")
                references = metadata.get("references") or metadata.get("reference")
                findings.append({
                    "rule_id": result.get("check_id"),
                    "severity": severity,
                    "message": result.get("extra", {}).get("message", ""),
                    "file": normalize_path(result.get("path", ""), self.root_path),
                    "line": result.get("start", {}).get("line"),
                    "category": self._categorize_security(result.get("check_id", "")),
                    "confidence": confidence,
                    "cwe": cwe,
                    "owasp": owasp,
                    "impact": impact,
                    "references": references,
                    "fingerprint": extra.get("fingerprint"),
                    "context": extra.get("lines", "")[:160],
                    "source": "semgrep",
                })
        return findings

    def _extract_endpoints(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        endpoints = []
        endpoint_keywords = ["route", "endpoint", "api", "http-method", "service"]
        for result in results.get("results", []):
            check_id = result.get("check_id", "").lower()
            if any(keyword in check_id for keyword in endpoint_keywords):
                extra = result.get("extra", {})
                metadata = extra.get("metadata", {})
                endpoints.append({
                    "file": normalize_path(result.get("path", ""), self.root_path),
                    "line": result.get("start", {}).get("line"),
                    "method": metadata.get("http_method", "UNKNOWN"),
                    "route": metadata.get("route", extra.get("lines", ""))[:120],
                    "framework": self._detect_framework(result.get("path", "")),
                    "source": "semgrep",
                })
        return endpoints

    def _extract_http_clients(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        clients = []
        for result in results.get("results", []):
            check_id = result.get("check_id", "")
            if "http-client" in check_id:
                metadata = result.get("extra", {}).get("metadata", {})
                clients.append({
                    "file": normalize_path(result.get("path", ""), self.root_path),
                    "line": result.get("start", {}).get("line"),
                    "library": metadata.get("library", check_id.split("-")[-1]),
                    "category": metadata.get("category", "http-client"),
                    "language": self._detect_language(result.get("path", "")),
                    "context": result.get("extra", {}).get("lines", "")[:120],
                    "source": "semgrep",
                })
        return clients

    def _extract_database_clients(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        db_clients = []
        for result in results.get("results", []):
            check_id = result.get("check_id", "")
            if "database" in check_id:
                metadata = result.get("extra", {}).get("metadata", {})
                db_clients.append({
                    "file": normalize_path(result.get("path", ""), self.root_path),
                    "line": result.get("start", {}).get("line"),
                    "type": self._detect_db_type(check_id),
                    "library": metadata.get("library", check_id.split("-")[-1]),
                    "orm": metadata.get("library", "unknown"),
                    "context": result.get("extra", {}).get("lines", "")[:120],
                    "source": "semgrep",
                })
        return db_clients

    def _extract_cache_clients(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        cache_clients = []
        for result in results.get("results", []):
            check_id = result.get("check_id", "")
            if "cache" in check_id.lower():
                metadata = result.get("extra", {}).get("metadata", {})
                cache_clients.append({
                    "file": normalize_path(result.get("path", ""), self.root_path),
                    "line": result.get("start", {}).get("line"),
                    "type": metadata.get("type", "redis" if "redis" in check_id else "memcached"),
                    "library": metadata.get("library", check_id.split("-")[-1]),
                    "context": result.get("extra", {}).get("lines", "")[:120],
                    "source": "semgrep",
                })
        return cache_clients

    def _extract_queue_clients(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        queue_clients = []
        for result in results.get("results", []):
            check_id = result.get("check_id", "")
            if "queue" in check_id.lower():
                metadata = result.get("extra", {}).get("metadata", {})
                queue_clients.append({
                    "file": normalize_path(result.get("path", ""), self.root_path),
                    "line": result.get("start", {}).get("line"),
                    "queue_type": metadata.get("type", self._detect_queue_type(check_id)),
                    "library": metadata.get("library", check_id.split("-")[-1]),
                    "direction": metadata.get("direction", "unknown"),
                    "source": "semgrep",
                })
        return queue_clients

    def _extract_grpc_clients(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        grpc_clients = []
        for result in results.get("results", []):
            check_id = result.get("check_id", "").lower()
            if "grpc" in check_id or "protobuf" in check_id:
                grpc_clients.append({
                    "file": normalize_path(result.get("path", ""), self.root_path),
                    "line": result.get("start", {}).get("line"),
                    "stub_name": result.get("extra", {}).get("metadata", {}).get("stub", "unknown"),
                    "source": "semgrep",
                })
        return grpc_clients

    def _categorize_security(self, rule_id: str) -> str:
        rule_lower = rule_id.lower()
        if "sql" in rule_lower or "injection" in rule_lower:
            return "injection"
        if "xss" in rule_lower or "cross-site" in rule_lower:
            return "xss"
        if "auth" in rule_lower or "jwt" in rule_lower:
            return "authentication"
        if "crypto" in rule_lower or "hash" in rule_lower:
            return "cryptography"
        if "secret" in rule_lower or "hardcoded" in rule_lower:
            return "secrets"
        return "other"

    def _detect_framework(self, file_path: str) -> str:
        if ".cs" in file_path:
            return "aspnet"
        if ".java" in file_path:
            return "spring"
        if ".go" in file_path:
            return "go"
        if ".cpp" in file_path or ".h" in file_path or ".cc" in file_path:
            return "thrift-cpp" if "thrift" in file_path.lower() else "cpp-service"
        if ".ts" in file_path or ".js" in file_path:
            return "node"
        if ".py" in file_path:
            return "python"
        return "unknown"

    def _detect_language(self, file_path: str) -> str:
        ext = Path(file_path).suffix
        language_map = {
            ".py": "python",
            ".cs": "csharp",
            ".java": "java",
            ".go": "go",
            ".ts": "typescript",
            ".js": "javascript",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".h": "cpp",
            ".hpp": "cpp",
            ".c": "c",
        }
        return language_map.get(ext, "unknown")

    def _detect_db_type(self, check_id: str) -> str:
        lower = check_id.lower()
        if "postgres" in lower or "pg" in lower:
            return "postgresql"
        if "mysql" in lower:
            return "mysql"
        if "mongo" in lower:
            return "mongodb"
        if "redis" in lower:
            return "redis"
        if "sql" in lower:
            return "sql"
        return "unknown"

    def _detect_queue_type(self, check_id: str) -> str:
        lower = check_id.lower()
        if "kafka" in lower:
            return "kafka"
        if "rabbitmq" in lower or "amqp" in lower:
            return "rabbitmq"
        if "sqs" in lower:
            return "aws_sqs"
        return "unknown"
