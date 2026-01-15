"""Tree-sitter based code structure analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils import normalize_path

try:
    from tree_sitter_languages import get_language, get_parser
except Exception:  # pragma: no cover
    get_language = None
    get_parser = None


class TreeSitterAnalyzer:
    """Analyze code structure using tree-sitter AST parsing."""

    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path).resolve()
        self.available = get_parser is not None
        self._parsers: Dict[str, Any] = {}
        self._languages: Dict[str, Any] = {}
        self.lang_map = {
            ".py": "python",
            ".cs": "c_sharp",
            ".java": "java",
            ".go": "go",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".js": "javascript",
            ".rb": "ruby",
            ".rs": "rust",
            ".php": "php",
            ".cpp": "cpp",
            ".c": "c",
        }

    def analyze(self) -> Dict[str, Any]:
        if not self.available:
            return {
                "available": False,
                "error": "tree_sitter_languages not installed",
                "classes": [],
                "interfaces": [],
                "functions": [],
                "metrics": {"total_files": 0, "total_classes": 0, "total_functions": 0},
            }

        results = {
            "available": True,
            "classes": [],
            "interfaces": [],
            "functions": [],
            "metrics": {"total_files": 0, "total_classes": 0, "total_functions": 0},
        }

        for file_path in self.root_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in self.lang_map:
                lang_name = self.lang_map[file_path.suffix]
                analysis = self._analyze_file(file_path, lang_name)
                if analysis:
                    results["classes"].extend(analysis.get("classes", []))
                    results["interfaces"].extend(analysis.get("interfaces", []))
                    results["functions"].extend(analysis.get("functions", []))
                    results["metrics"]["total_files"] += 1

        results["metrics"]["total_classes"] = len(results["classes"])
        results["metrics"]["total_functions"] = len(results["functions"])
        return results

    def _get_parser(self, lang_name: str):
        if lang_name not in self._parsers:
            try:
                self._parsers[lang_name] = get_parser(lang_name)
                self._languages[lang_name] = get_language(lang_name)
            except Exception:
                return None
        return self._parsers.get(lang_name)

    def _analyze_file(self, file_path: Path, lang_name: str) -> Optional[Dict[str, Any]]:
        parser = self._get_parser(lang_name)
        if not parser:
            return None

        try:
            content = file_path.read_bytes()
            tree = parser.parse(content)
            root_node = tree.root_node
        except Exception:
            return None

        file_info = {
            "file": normalize_path(file_path, self.root_path),
            "language": lang_name,
            "classes": [],
            "interfaces": [],
            "functions": [],
        }

        if lang_name == "c_sharp":
            query_str = """
            (class_declaration name: (identifier) @name) @class
            (interface_declaration name: (identifier) @name) @interface
            (method_declaration name: (identifier) @name) @method
            """
        elif lang_name == "java":
            query_str = """
            (class_declaration name: (identifier) @name) @class
            (interface_declaration name: (identifier) @name) @interface
            (method_declaration name: (identifier) @name) @method
            """
        elif lang_name == "go":
            query_str = """
            (type_declaration (type_spec name: (type_identifier) @name type: (struct_type))) @class
            (type_declaration (type_spec name: (type_identifier) @name type: (interface_type))) @interface
            (function_declaration name: (identifier) @name) @method
            (method_declaration name: (field_identifier) @name) @method
            """
        elif lang_name in {"typescript", "tsx", "javascript"}:
            if lang_name in {"typescript", "tsx"}:
                query_str = """
                (class_declaration name: (type_identifier) @name) @class
                (interface_declaration name: (type_identifier) @name) @interface
                (function_declaration name: (identifier) @name) @method
                (method_definition name: (property_identifier) @name) @method
                """
            else:
                query_str = """
                (class_declaration name: (identifier) @name) @class
                (function_declaration name: (identifier) @name) @method
                (method_definition name: (property_identifier) @name) @method
                """
        elif lang_name == "python":
            query_str = """
            (class_definition name: (identifier) @name) @class
            (function_definition name: (identifier) @name) @method
            """
        else:
            return file_info

        self._run_query(query_str, lang_name, root_node, content, file_info)
        return file_info

    def _run_query(self, query_str: str, lang_name: str, node, content: bytes, info: Dict[str, Any]) -> None:
        try:
            language = self._languages[lang_name]
            query = language.query(query_str)
            captures = query.captures(node)
            processed = set()

            for capture_node, name in captures:
                if capture_node.id in processed:
                    continue
                if name == "class":
                    name_text = self._node_name(capture_node, content)
                    info["classes"].append({
                        "name": name_text,
                        "file": info["file"],
                        "line": capture_node.start_point[0] + 1,
                    })
                elif name == "interface":
                    name_text = self._node_name(capture_node, content)
                    info["interfaces"].append({
                        "name": name_text,
                        "file": info["file"],
                        "line": capture_node.start_point[0] + 1,
                    })
                elif name == "method":
                    name_text = self._node_name(capture_node, content)
                    info["functions"].append({
                        "name": name_text,
                        "file": info["file"],
                        "line": capture_node.start_point[0] + 1,
                    })
                processed.add(capture_node.id)
        except Exception:
            return None

    def _node_name(self, node, content: bytes) -> str:
        for child in node.children:
            if "identifier" in child.type:
                return content[child.start_byte:child.end_byte].decode("utf-8", errors="ignore")
        return "Unknown"
