"""Pydantic models for the StaticAnalysisAgent output.

`StaticAnalysisReport` is the structured deliverable that the agent emits and
that downstream agents (AnalyzerAgent, OptimizerAgent) consume. Keeping it
language-agnostic was a deliberate choice: every finding carries `language`
and `category` so heterogeneous benchmarks can produce a single report.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Finding(BaseModel):
    """A single static-analysis finding produced by a rendered template.

    Findings are deliberately flat (no nested `result` object) so they
    serialise cleanly to JSON for the analyzer agent's payload.
    """

    rule_id: str = Field(description="Unique rule identifier (matches the .ql @id)")
    category: str = Field(
        description="Taxonomy category, e.g. 'concurrency', 'serialization', 'structural'"
    )
    taxonomy_entry: str = Field(
        description="Taxonomy entry id that produced this finding, e.g. 'antipattern.synchronization'"
    )
    language: str = Field(description="Source language: 'java', 'cpp', or 'python'")
    location: str = Field(
        description="Symbol/file location, e.g. 'foo.bar.Baz.run' or 'src/server.cc:42'"
    )
    evidence: str = Field(
        description="Key=value pairs from the SARIF message, joined with '|'"
    )
    severity: str = Field(default="info", description="info | warning | error")
    properties: dict = Field(
        default_factory=dict,
        description="Parsed key/value pairs from the SARIF message text",
    )


class TaxonomyCoverage(BaseModel):
    """Records which taxonomy categories were attempted, skipped, or failed.

    Without this, the analyzer cannot distinguish between "nothing was found"
    and "we never looked for it" — which is the central reason ad-hoc
    CodeQL is unreliable.
    """

    entry_id: str
    language: str
    status: str = Field(description="run | skipped | error")
    findings_count: int = 0
    skip_reason: Optional[str] = None
    error: Optional[str] = None


class CustomQueryRecord(BaseModel):
    """Tracks LLM-authored hypothesis queries for reproducibility."""

    hypothesis: str
    language: str
    query_text: str
    rule_id: str
    findings_count: int
    compiled: bool = True
    error: Optional[str] = None


class BenchmarkSummary(BaseModel):
    """Compact view of the fingerprint to embed in the report.

    The full fingerprint is also written to disk; this is the human-readable
    slice the analyzer agent will read most often.
    """

    repo_path: str
    languages: List[str]
    primary_language: str
    package_filters: dict = Field(
        default_factory=dict,
        description="Per-language placeholder used by templates (e.g. java -> 'tools.descartes.teastore.%')",
    )
    frameworks: List[str] = Field(default_factory=list)
    build_systems: List[str] = Field(default_factory=list)


class StaticAnalysisReport(BaseModel):
    """Top-level structured output of the StaticAnalysisAgent."""

    benchmark: BenchmarkSummary
    taxonomy_findings: List[Finding] = Field(default_factory=list)
    hypothesis_findings: List[Finding] = Field(default_factory=list)
    coverage: List[TaxonomyCoverage] = Field(default_factory=list)
    custom_queries: List[CustomQueryRecord] = Field(default_factory=list)
    notes: List[str] = Field(
        default_factory=list,
        description="Free-form caveats: what was skipped, where templates fell back, etc.",
    )
