"""CodeQLAgent for running CodeQL analysis and returning outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agents.base import BaseAgent
from static_analisis_tools.codeql import run_codeql_local


class CodeQLRunResult(BaseModel):
    """Structured CodeQL execution output."""

    root: Optional[str] = Field(default=None, description="CodeQL source root")
    target: Optional[str] = Field(default=None, description="Target path under root")
    output_base: Optional[str] = Field(default=None, description="Output directory")
    queries_path: Optional[str] = Field(default=None, description="Queries directory")
    language: Optional[str] = Field(default=None, description="Detected language")
    build_command: Optional[str] = Field(default=None, description="Build command")
    db_path: Optional[str] = Field(default=None, description="CodeQL DB path")
    sarif_files: List[str] = Field(default_factory=list, description="SARIF outputs")
    summary_path: Optional[str] = Field(default=None, description="output.json path")
    notes: List[str] = Field(default_factory=list, description="Run notes or errors")


class CodeQLAgent(BaseAgent):
    """Agent that runs CodeQL and reports output paths."""

    prompt = """You run CodeQL analysis and report output paths for optimization analysis.

Input is either:
- A JSON object with keys:
  - codeql_source (optional): path to output.json or a directory containing it
  - codeql_src (optional): root path for running CodeQL
  - codeql_rel_path (optional): relative path within codeql_src
  - codeql_output (optional): output directory for CodeQL results
  - codeql_queries (optional): queries directory
- A plain string path, which should be treated as codeql_source

codeql_source points to a CodeQL summary JSON or a directory containing output.json.
If codeql_source is missing and codeql_src is provided, run CodeQL first.
If codeql_source looks like a directory, set summary_path to codeql_source/output.json.

## Tool Strategy
1) If codeql_source is missing and codeql_src is set, call run_codeql_local.
2) If codeql_source is provided, return it as summary_path with a short note.

## Output Requirements
- Return JSON matching CodeQLRunResult.
- Keep notes short and concrete (no speculation).
- Do not propose fixes here.
"""

    structured_output_type = CodeQLRunResult
    return_state_field = "codeql_summary"
    temperature = 0.3
    max_iterations = 6

    tools = [
        run_codeql_local,
    ]

    async def run(self, input_text: str, **invoke_kwargs: Any) -> str:
        payload = self._prepare_input_payload(input_text)
        if isinstance(payload, dict):
            input_text = json.dumps(payload)
        return await super().run(input_text, **invoke_kwargs)

    def _prepare_input_payload(self, input_text: str) -> Dict[str, Any] | None:
        stripped = input_text.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        target_path = Path(stripped).expanduser().resolve()
        if not target_path.exists() or not target_path.is_dir():
            return None

        parent = target_path.parent
        if (
            (parent / "deps").exists()
            or (parent / "local_include").exists()
            or (parent / "local_lib").exists()
        ):
            return {"codeql_src": str(target_path), "codeql_rel_path": "."}

        return {"codeql_src": str(parent), "codeql_rel_path": target_path.name}
