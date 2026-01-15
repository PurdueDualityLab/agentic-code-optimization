"""Python-specific static analysis using AST and lightweight heuristics."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import LanguageAnalyzer
from .utils import normalize_path, safe_run, which


class PythonAnalyzer(LanguageAnalyzer):
    """Static analyzer for Python projects."""

    def __init__(self, root_path: str | Path, max_files: int = 400) -> None:
        super().__init__(root_path)
        python_files = list(self.root_path.rglob("*.py"))
        self.python_files = [
            f for f in python_files
            if not any(part in f.parts for part in [
                ".venv", "venv", "__pycache__", ".git", "node_modules",
                ".tox", ".pytest_cache", "build", "dist",
            ])
        ]
        self.python_files = self.python_files[:max_files]

    def analyze(self) -> Dict[str, Any]:
        self.results = {
            "language": "python",
            "files_analyzed": len(self.python_files),
            "call_graph": self.extract_call_graph(),
            "imports": self.extract_imports(),
            "dependencies": self.extract_dependency_graph(),
            "type_analysis": self.extract_type_analysis(),
            "http_clients": self.detect_http_clients(),
            "grpc_clients": self.detect_grpc_clients(),
            "queue_clients": self.detect_queue_clients(),
            "database_clients": self.detect_database_clients(),
            "cache_clients": self.detect_cache_clients(),
            "storage_clients": self.detect_storage_clients(),
            "endpoints": self.detect_endpoints(),
        }
        return self.results

    def extract_call_graph(self) -> Dict[str, Any]:
        call_graph = {"nodes": [], "edges": []}
        for py_file in self.python_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(py_file))
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    node_id = f"{normalize_path(py_file, self.root_path)}:{node.name}:{node.lineno}"
                    call_graph["nodes"].append({
                        "id": node_id,
                        "name": node.name,
                        "file": normalize_path(py_file, self.root_path),
                        "line": node.lineno,
                        "type": "function",
                    })

                    for inner in ast.walk(node):
                        if isinstance(inner, ast.Call):
                            call_name = self._get_call_name(inner)
                            if call_name:
                                call_graph["edges"].append({
                                    "from_id": node_id,
                                    "to_name": call_name,
                                    "file": normalize_path(py_file, self.root_path),
                                    "line": getattr(inner, "lineno", node.lineno),
                                    "call_type": "direct",
                                })

                elif isinstance(node, ast.ClassDef):
                    node_id = f"{normalize_path(py_file, self.root_path)}:{node.name}:{node.lineno}"
                    call_graph["nodes"].append({
                        "id": node_id,
                        "name": node.name,
                        "file": normalize_path(py_file, self.root_path),
                        "line": node.lineno,
                        "type": "class",
                    })

        call_graph["node_count"] = len(call_graph["nodes"])
        call_graph["edge_count"] = len(call_graph["edges"])
        return call_graph

    def extract_imports(self) -> List[Dict[str, Any]]:
        imports: List[Dict[str, Any]] = []
        for py_file in self.python_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(py_file))
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append({
                            "file": normalize_path(py_file, self.root_path),
                            "line": node.lineno,
                            "type": "import",
                            "module": alias.name,
                            "alias": alias.asname,
                        })
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        imports.append({
                            "file": normalize_path(py_file, self.root_path),
                            "line": node.lineno,
                            "type": "from_import",
                            "module": module,
                            "name": alias.name,
                            "alias": alias.asname,
                        })

        return imports

    def extract_dependency_graph(self) -> Dict[str, Any]:
        dependencies: Dict[str, Any] = {"packages": [], "sources": []}

        req_files = list(self.root_path.rglob("requirements*.txt"))
        for req_file in req_files:
            try:
                for line in req_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        pkg_match = re.match(r"^([a-zA-Z0-9_\-]+)", line)
                        if pkg_match:
                            dependencies["packages"].append({
                                "name": pkg_match.group(1),
                                "source": normalize_path(req_file, self.root_path),
                                "spec": line,
                            })
                dependencies["sources"].append(normalize_path(req_file, self.root_path))
            except Exception:
                continue

        pyproject_files = list(self.root_path.rglob("pyproject.toml"))
        for pyproject in pyproject_files:
            try:
                import tomllib
            except Exception:
                tomllib = None

            if not tomllib:
                continue

            try:
                data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
                if "project" in data:
                    for dep in data["project"].get("dependencies", []):
                        pkg_match = re.match(r"^([a-zA-Z0-9_\-]+)", dep)
                        if pkg_match:
                            dependencies["packages"].append({
                                "name": pkg_match.group(1),
                                "source": normalize_path(pyproject, self.root_path),
                                "spec": dep,
                            })
                if "tool" in data and "poetry" in data["tool"]:
                    poetry_deps = data["tool"]["poetry"].get("dependencies", {})
                    for pkg, spec in poetry_deps.items():
                        if pkg == "python":
                            continue
                        dependencies["packages"].append({
                            "name": pkg,
                            "source": normalize_path(pyproject, self.root_path),
                            "spec": str(spec),
                        })
                dependencies["sources"].append(normalize_path(pyproject, self.root_path))
            except Exception:
                continue

        return dependencies

    def detect_http_clients(self) -> List[Dict[str, Any]]:
        http_clients: List[Dict[str, Any]] = []
        patterns = [
            (r"requests\.(get|post|put|patch|delete|request)\s*\(", "requests"),
            (r"httpx\.(get|post|put|patch|delete|request|Client|AsyncClient)", "httpx"),
            (r"aiohttp\.ClientSession", "aiohttp"),
            (r"urllib\.request\.(urlopen|Request)", "urllib"),
        ]

        for py_file in self.python_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern, library in patterns:
                for match in re.finditer(pattern, source):
                    line_num = source[:match.start()].count("\n") + 1
                    url_match = re.search(r"['\"]https?://([^'\"]+)['\"]", source[match.start():match.start()+200])
                    url = url_match.group(1) if url_match else None
                    http_clients.append({
                        "file": normalize_path(py_file, self.root_path),
                        "line": line_num,
                        "library": library,
                        "method": match.group(1) if match.lastindex else None,
                        "url_hint": url,
                        "source": "python_ast",
                    })

        return http_clients

    def detect_grpc_clients(self) -> List[Dict[str, Any]]:
        grpc_clients: List[Dict[str, Any]] = []
        for py_file in self.python_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            if "import grpc" in source or "from grpc" in source:
                stub_pattern = r"(\w+)Stub\s*\("
                for match in re.finditer(stub_pattern, source):
                    line_num = source[:match.start()].count("\n") + 1
                    grpc_clients.append({
                        "file": normalize_path(py_file, self.root_path),
                        "line": line_num,
                        "stub_name": match.group(1) + "Stub",
                        "source": "python_ast",
                    })

        return grpc_clients

    def detect_queue_clients(self) -> List[Dict[str, Any]]:
        queue_clients: List[Dict[str, Any]] = []
        patterns = [
            (r"KafkaProducer|KafkaConsumer", "kafka", r"kafka"),
            (r"pika\.BlockingConnection|pika\.channel", "rabbitmq", r"pika"),
            (r"boto3\.client\(['\"]sqs['\"]\)", "aws_sqs", r"boto3"),
        ]

        for py_file in self.python_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern, queue_type, import_pattern in patterns:
                if re.search(import_pattern, source):
                    for match in re.finditer(pattern, source):
                        line_num = source[:match.start()].count("\n") + 1
                        role = "producer" if "Producer" in match.group() else "consumer" if "Consumer" in match.group() else "client"
                        queue_clients.append({
                            "file": normalize_path(py_file, self.root_path),
                            "line": line_num,
                            "queue_type": queue_type,
                            "role": role,
                            "source": "python_ast",
                        })

        return queue_clients

    def detect_database_clients(self) -> List[Dict[str, Any]]:
        db_clients: List[Dict[str, Any]] = []
        patterns = [
            (r"sqlalchemy\.create_engine|sessionmaker", "sqlalchemy", "sql"),
            (r"psycopg2\.connect", "psycopg2", "postgresql"),
            (r"pymongo\.MongoClient", "pymongo", "mongodb"),
            (r"redis\.Redis|redis\.StrictRedis", "redis-py", "redis"),
            (r"mysql\.connector\.connect", "mysql-connector", "mysql"),
        ]

        for py_file in self.python_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern, library, db_type in patterns:
                for match in re.finditer(pattern, source):
                    line_num = source[:match.start()].count("\n") + 1
                    db_clients.append({
                        "file": normalize_path(py_file, self.root_path),
                        "line": line_num,
                        "library": library,
                        "type": db_type,
                        "source": "python_ast",
                    })

        return db_clients

    def detect_cache_clients(self) -> List[Dict[str, Any]]:
        cache_clients: List[Dict[str, Any]] = []
        patterns = [
            (r"redis\.Redis|redis\.StrictRedis|redis\.from_url", "redis"),
            (r"memcache\.Client|pylibmc\.Client", "memcached"),
        ]

        for py_file in self.python_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern, cache_type in patterns:
                for match in re.finditer(pattern, source):
                    line_num = source[:match.start()].count("\n") + 1
                    cache_clients.append({
                        "file": normalize_path(py_file, self.root_path),
                        "line": line_num,
                        "type": cache_type,
                        "source": "python_ast",
                    })

        return cache_clients

    def detect_storage_clients(self) -> List[Dict[str, Any]]:
        storage_clients: List[Dict[str, Any]] = []
        patterns = [
            (r"boto3\.client\(['\"]s3['\"]\)|boto3\.resource\(['\"]s3['\"]\)", "aws_s3"),
            (r"BlobServiceClient|BlobClient", "azure_blob"),
            (r"storage\.Client\(\)|storage\.Bucket", "gcs"),
        ]

        for py_file in self.python_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern, storage_type in patterns:
                for match in re.finditer(pattern, source):
                    line_num = source[:match.start()].count("\n") + 1
                    storage_clients.append({
                        "file": normalize_path(py_file, self.root_path),
                        "line": line_num,
                        "type": storage_type,
                        "source": "python_ast",
                    })

        return storage_clients

    def detect_endpoints(self) -> List[Dict[str, Any]]:
        endpoints: List[Dict[str, Any]] = []
        for py_file in self.python_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            fastapi_pattern = r"@app\.(get|post|put|patch|delete)\(['\"]([^'\"]+)['\"]\)"
            for match in re.finditer(fastapi_pattern, source):
                line_num = source[:match.start()].count("\n") + 1
                endpoints.append({
                    "file": normalize_path(py_file, self.root_path),
                    "line": line_num,
                    "framework": "fastapi",
                    "method": match.group(1).upper(),
                    "route": match.group(2),
                    "source": "python_ast",
                })

            flask_pattern = r"@app\.route\(['\"]([^'\"]+)['\"](?:,\s*methods=\[([^\]]+)\])?"
            for match in re.finditer(flask_pattern, source):
                line_num = source[:match.start()].count("\n") + 1
                methods = match.group(2) if match.group(2) else "GET"
                for method in re.findall(r"['\"](\w+)['\"]", methods):
                    endpoints.append({
                        "file": normalize_path(py_file, self.root_path),
                        "line": line_num,
                        "framework": "flask",
                        "method": method.upper(),
                        "route": match.group(1),
                        "source": "python_ast",
                    })

            django_pattern = r"path\(['\"]([^'\"]+)['\"]"
            for match in re.finditer(django_pattern, source):
                line_num = source[:match.start()].count("\n") + 1
                endpoints.append({
                    "file": normalize_path(py_file, self.root_path),
                    "line": line_num,
                    "framework": "django",
                    "method": "GET",
                    "route": "/" + match.group(1),
                    "source": "python_ast",
                })

        return endpoints

    def extract_type_analysis(self) -> Dict[str, Any]:
        type_analysis = {
            "tool": None,
            "errors": [],
            "warnings": [],
            "type_coverage": None,
        }

        if which("pyright"):
            code, stdout, _stderr = safe_run(["pyright", "--outputjson", str(self.root_path)], 120)
            if code in (0, 1) and stdout:
                try:
                    output = json.loads(stdout)
                except Exception:
                    return type_analysis
                type_analysis["tool"] = "pyright"
                type_analysis["version"] = output.get("version", "unknown")
                diagnostics = output.get("generalDiagnostics", [])
                for diag in diagnostics[:100]:
                    item = {
                        "file": diag.get("file", ""),
                        "line": diag.get("range", {}).get("start", {}).get("line", 0) + 1,
                        "severity": diag.get("severity", ""),
                        "message": diag.get("message", ""),
                    }
                    if diag.get("severity") == "error":
                        type_analysis["errors"].append(item)
                    else:
                        type_analysis["warnings"].append(item)

                summary = output.get("summary", {})
                type_analysis["type_coverage"] = {
                    "files_analyzed": summary.get("filesAnalyzed", 0),
                    "errors": summary.get("errorCount", 0),
                    "warnings": summary.get("warningCount", 0),
                }
                return type_analysis

        if which("mypy"):
            code, stdout, _stderr = safe_run(["mypy", "--show-error-codes", "--no-incremental", str(self.root_path)], 120)
            type_analysis["tool"] = "mypy"
            for line in stdout.splitlines()[:100]:
                match = re.match(r"([^:]+):(\d+):\s*(error|warning|note):\s*(.+)", line)
                if match:
                    item = {
                        "file": match.group(1),
                        "line": int(match.group(2)),
                        "severity": match.group(3),
                        "message": match.group(4),
                    }
                    if match.group(3) == "error":
                        type_analysis["errors"].append(item)
                    else:
                        type_analysis["warnings"].append(item)

            return type_analysis

        type_analysis["tool"] = "not_available"
        return type_analysis

    def _get_call_name(self, call_node: ast.Call) -> Optional[str]:
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        if isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr
        return None
