"""Generic, language-agnostic CodeQL static analysis package.

This package replaces the benchmark-specific hardcoded queries in
`tools/codeql.py` (TeaStore/Java) and `tools/codeql_cpp.py` (DeathStarBench/C++)
with a pluggable framework that:

1. **Fingerprints** an arbitrary repository to discover its language(s),
   package/source roots, and frameworks.
2. **Renders** CodeQL queries from vetted, parameterised templates organised
   by a cross-language performance anti-pattern **taxonomy**.
3. **Executes** queries against a CodeQL database (with caching) and parses
   SARIF results into structured `Finding` records.
4. **Surfaces** the building blocks as LangChain `@tool` callables so a
   `StaticAnalysisAgent` can drive the analysis declaratively.

The package is intentionally written so a new benchmark in any supported
language requires only a fingerprint pass — no code changes.
"""

from tools.codeql.fingerprint import (BenchmarkFingerprint,
                                       fingerprint_repository)
from tools.codeql.report import Finding, StaticAnalysisReport
from tools.codeql.taxonomy import (TAXONOMY, TaxonomyEntry,
                                    list_taxonomy_entries)
from tools.codeql.tools import (author_custom_codeql_query,
                                 fingerprint_benchmark,
                                 list_taxonomy,
                                 render_taxonomy_query,
                                 run_taxonomy_pass)

__all__ = [
    "BenchmarkFingerprint",
    "Finding",
    "StaticAnalysisReport",
    "TAXONOMY",
    "TaxonomyEntry",
    "fingerprint_repository",
    "list_taxonomy_entries",
    # Tools
    "author_custom_codeql_query",
    "fingerprint_benchmark",
    "list_taxonomy",
    "render_taxonomy_query",
    "run_taxonomy_pass",
]
from tools.codeql.legacy import teastore_behavior_analysis, teastore_component_analysis
