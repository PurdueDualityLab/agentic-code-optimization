"""Cross-language performance anti-pattern taxonomy.

This is the **systematic** part of the static-analysis pass. Instead of
running an arbitrary set of queries the LLM dreams up, the agent walks
this taxonomy:

  Stage 1 (structural backbone):
    - structural.services      — service/component identification
    - structural.endpoints     — externally-reachable entry points
    - structural.call_graph    — coarse call edges across services

  Stage 2 (anti-pattern probes):
    - antipattern.synchronization
    - antipattern.http_client_construction
    - antipattern.serialization_per_request
    - antipattern.string_concat_in_loop
    - antipattern.db_access_sites
    - antipattern.logging_in_hot_path

Each entry maps to one .ql template per supported language. Adding a new
template is a two-file change (the .ql and one entry below). Adding a new
language for an existing taxonomy entry is a one-file change (the .ql).

Skipping is recorded explicitly: if a benchmark has no JDBC dependency,
`antipattern.db_access_sites` is recorded as `skipped` with a reason —
the analyzer can then distinguish "no DB hotspots" from "we never looked".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from tools.codeql.fingerprint import BenchmarkFingerprint


@dataclass(frozen=True)
class TaxonomyEntry:
    """One row of the analysis taxonomy.

    Attributes:
        id: Unique identifier (e.g. 'antipattern.synchronization').
        category: Coarse grouping ('structural', 'concurrency', 'io', ...).
        description: Short explainer (used in tool docs and the report).
        languages: Languages we have a template for. If a fingerprint
            language is not in this set, the entry is skipped.
        templates: Per-language path (relative to `templates/`) of the
            .ql file to render.
        rule_id_format: Format string for the .ql `@id`. Templates use
            `${RULE_ID}` to inject this; substitution happens in the
            renderer using the language adapter's `RULE_PREFIX`.
        framework_gates: Optional. If set, the entry is *only* run when
            *any* of these frameworks appears in the fingerprint for the
            language. Used to skip e.g. JDBC analysis on a repo that has
            no JDBC dependency.
    """

    id: str
    category: str
    description: str
    languages: frozenset[str]
    templates: dict[str, str]
    rule_id_format: str
    framework_gates: dict[str, frozenset[str]] = field(default_factory=dict)

    def applicable_to(
        self, language: str, fingerprint: BenchmarkFingerprint
    ) -> tuple[bool, Optional[str]]:
        """Return (applicable, skip_reason)."""
        if language not in self.languages:
            return False, f"no template for language={language}"
        gates = self.framework_gates.get(language)
        if gates:
            present = set(fingerprint.frameworks.get(language, []))
            if not (present & gates):
                return (
                    False,
                    f"none of the gating frameworks present "
                    f"(needed any of {sorted(gates)}, found {sorted(present)})",
                )
        return True, None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TAXONOMY: list[TaxonomyEntry] = [
    # ---- Stage 1: structural backbone ------------------------------------
    TaxonomyEntry(
        id="structural.services",
        category="structural",
        description=(
            "Identify service-like classes/components — the units that hold "
            "business logic and are addressable from outside their service."
        ),
        languages=frozenset({"java", "cpp", "python"}),
        templates={
            "java": "java/structural/services.ql",
            "cpp": "cpp/structural/services.ql",
            "python": "python/structural/services.ql",
        },
        rule_id_format="aco/${RULE_PREFIX}/structural-services",
    ),
    TaxonomyEntry(
        id="structural.endpoints",
        category="structural",
        description=(
            "Externally-reachable entry points (HTTP endpoints, RPC handlers, "
            "framework routes). Subset of services that the rest of the system "
            "talks to."
        ),
        languages=frozenset({"java", "cpp", "python"}),
        templates={
            "java": "java/structural/endpoints.ql",
            "cpp": "cpp/structural/endpoints.ql",
            "python": "python/structural/endpoints.ql",
        },
        rule_id_format="aco/${RULE_PREFIX}/structural-endpoints",
    ),
    TaxonomyEntry(
        id="structural.call_graph",
        category="structural",
        description=(
            "Class/function-level call edges within the benchmark. Anchors "
            "all subsequent anti-pattern findings to architectural context."
        ),
        languages=frozenset({"java", "cpp", "python"}),
        templates={
            "java": "java/structural/call_graph.ql",
            "cpp": "cpp/structural/call_graph.ql",
            "python": "python/structural/call_graph.ql",
        },
        rule_id_format="aco/${RULE_PREFIX}/structural-call-graph",
    ),
    # ---- Stage 2: anti-patterns -----------------------------------------
    TaxonomyEntry(
        id="antipattern.synchronization",
        category="concurrency",
        description=(
            "Synchronisation constructs that are common contention hotspots: "
            "synchronized methods/blocks (Java), std::lock_guard / unique_lock "
            "(C++), threading.Lock acquisitions (Python)."
        ),
        languages=frozenset({"java", "cpp", "python"}),
        templates={
            "java": "java/antipatterns/synchronization.ql",
            "cpp": "cpp/antipatterns/synchronization.ql",
            "python": "python/antipatterns/synchronization.ql",
        },
        rule_id_format="aco/${RULE_PREFIX}/antipattern-synchronization",
    ),
    TaxonomyEntry(
        id="antipattern.http_client_construction",
        category="io",
        description=(
            "HTTP client objects (HttpClient, OkHttpClient, requests.Session) "
            "constructed *inside* methods rather than reused as singletons. "
            "Classic latency tax."
        ),
        languages=frozenset({"java", "python"}),
        templates={
            "java": "java/antipatterns/http_client_construction.ql",
            "python": "python/antipatterns/http_client_construction.ql",
        },
        rule_id_format="aco/${RULE_PREFIX}/antipattern-http-client-construction",
        framework_gates={
            "java": frozenset({"okhttp", "apache-httpclient", "spring", "springboot"}),
            "python": frozenset({"requests", "aiohttp", "fastapi", "flask"}),
        },
    ),
    TaxonomyEntry(
        id="antipattern.serialization_per_request",
        category="io",
        description=(
            "JSON/XML serialiser objects (ObjectMapper, Gson) allocated per "
            "request rather than reused — repeated reflection/init cost."
        ),
        languages=frozenset({"java"}),
        templates={
            "java": "java/antipatterns/serialization_per_request.ql",
        },
        rule_id_format="aco/${RULE_PREFIX}/antipattern-serialization-per-request",
        framework_gates={
            "java": frozenset({"jackson", "gson"}),
        },
    ),
    TaxonomyEntry(
        id="antipattern.string_concat_in_loop",
        category="allocation",
        description=(
            "String concatenation with `+` inside loops — quadratic in many "
            "runtimes, fixable with builders/joiners."
        ),
        languages=frozenset({"java", "python"}),
        templates={
            "java": "java/antipatterns/string_concat_in_loop.ql",
            "python": "python/antipatterns/string_concat_in_loop.ql",
        },
        rule_id_format="aco/${RULE_PREFIX}/antipattern-string-concat-in-loop",
    ),
    TaxonomyEntry(
        id="antipattern.db_access_sites",
        category="database",
        description=(
            "Sites that issue DB calls. Surface for the analyzer to investigate "
            "N+1 queries, missing prepared statements, batching opportunities."
        ),
        languages=frozenset({"java", "python"}),
        templates={
            "java": "java/antipatterns/db_access_sites.ql",
            "python": "python/antipatterns/db_access_sites.ql",
        },
        rule_id_format="aco/${RULE_PREFIX}/antipattern-db-access-sites",
        framework_gates={
            "java": frozenset({"jdbc", "jpa", "hibernate"}),
            "python": frozenset({"sqlalchemy", "django"}),
        },
    ),
    TaxonomyEntry(
        id="antipattern.logging_in_hot_path",
        category="logging",
        description=(
            "Log statements with eagerly-built messages (string concat, "
            ".format) inside loops or per-request paths."
        ),
        languages=frozenset({"java", "python"}),
        templates={
            "java": "java/antipatterns/logging_in_hot_path.ql",
            "python": "python/antipatterns/logging_in_hot_path.ql",
        },
        rule_id_format="aco/${RULE_PREFIX}/antipattern-logging-in-hot-path",
        framework_gates={
            "java": frozenset({"log4j"}),
        },
    ),
]


def list_taxonomy_entries() -> list[dict]:
    """Return a JSON-serialisable view of the taxonomy for the agent."""
    return [
        {
            "id": e.id,
            "category": e.category,
            "description": e.description,
            "languages": sorted(e.languages),
            "framework_gates": {
                k: sorted(v) for k, v in e.framework_gates.items()
            },
        }
        for e in TAXONOMY
    ]


def get_entry(entry_id: str) -> Optional[TaxonomyEntry]:
    for e in TAXONOMY:
        if e.id == entry_id:
            return e
    return None
