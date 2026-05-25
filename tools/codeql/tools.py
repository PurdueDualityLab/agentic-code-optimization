"""LangChain @tool wrappers around the codeql package.

These are the entry points the StaticAnalysisAgent's prompt names. Each
returns a JSON string so the agent can read structured fields back; long
text shells are deliberately avoided.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from langchain_core.tools import tool

from tools.codeql.fingerprint import fingerprint_repository
from tools.codeql.pipeline import run_custom_query, run_taxonomy
from tools.codeql.render import TemplateRenderError, render_by_id
from tools.codeql.taxonomy import list_taxonomy_entries

logger = logging.getLogger(__name__)


@tool
def fingerprint_benchmark(repo_path: str) -> str:
    """Inspect a repository to discover its languages, source roots, frameworks
    and build systems. Pure filesystem inspection — does not invoke CodeQL.

    Always call this first. The fingerprint is what makes every downstream
    template parameterised: the same `synchronization` template adapts to
    `tools.descartes.teastore.%` for TeaStore and `socialNetwork/src/%`
    for DeathStarBench, no code changes needed.

    Args:
        repo_path: Absolute path to the repository root.

    Returns:
        JSON object: { repo_path, languages, primary_language, file_counts,
        line_counts, source_roots, package_filters, frameworks, build_systems,
        notes }.
    """
    fp = fingerprint_repository(repo_path)
    return fp.to_json()


@tool
def list_taxonomy() -> str:
    """List the cross-language performance anti-pattern taxonomy.

    Returns the catalogue of analysis entries the agent can run, each with:
    id, category, description, supported languages, and any framework gates
    (e.g. db-related entries are skipped on a repo with no DB framework).

    Use this once after fingerprinting to plan which categories are worth
    running given what the fingerprint discovered.

    Returns:
        JSON list of taxonomy entries.
    """
    return json.dumps(list_taxonomy_entries(), indent=2)


@tool
def render_taxonomy_query(entry_id: str, language: str, repo_path: str) -> str:
    """Render the .ql query text for a single taxonomy entry against a repo.

    Use this when you want to *inspect* the exact query that would be run —
    e.g. to confirm the package filter is correct before running a slow
    pass, or to use the rendered text as a starting point for a custom
    hypothesis query.

    Args:
        entry_id: Taxonomy entry id, e.g. 'antipattern.synchronization'.
        language: One of the supported languages ('java'|'cpp'|'python').
        repo_path: Repository root (used to compute the fingerprint).

    Returns:
        JSON: { rule_id, query, error?, available_entry_ids? }
    """
    fp = fingerprint_repository(repo_path)
    try:
        query_text, rule_id = render_by_id(entry_id, language, fp)
        return json.dumps({"rule_id": rule_id, "query": query_text})
    except TemplateRenderError as e:
        return json.dumps(
            {
                "error": str(e),
                "available_entry_ids": [
                    e["id"] for e in list_taxonomy_entries()
                ],
            }
        )


@tool
def run_taxonomy_pass(
    repo_path: str,
    only_categories: Optional[list[str]] = None,
    only_languages: Optional[list[str]] = None,
    backend: str = "auto",
) -> str:
    """Execute the systematic taxonomy pass against the repository.

    For every taxonomy entry applicable to each detected language (after
    framework-gate filtering), render the template, execute via CodeQL,
    parse SARIF, and return the structured report.

    Coverage records are emitted for *every* (entry, language) pair —
    including skipped ones — so the analyzer can distinguish "found
    nothing" from "didn't look".

    Args:
        repo_path: Repository root.
        only_categories: Optional whitelist of categories. Useful for
            running just the structural backbone first
            (`['structural']`) and the anti-pattern probes second.
        only_languages: Optional whitelist of languages.
        backend: 'auto' | 'local' | 'docker'. 'auto' picks `codeql` CLI
            if on PATH, else the codeql-agent Docker image.

    Returns:
        JSON-serialised StaticAnalysisReport (without hypothesis findings).
    """
    report = run_taxonomy(
        repo_path=repo_path,
        only_categories=only_categories,
        only_languages=only_languages,
        backend=backend,
    )
    return report.model_dump_json(indent=2)


@tool
def author_custom_codeql_query(
    repo_path: str,
    language: str,
    query_text: str,
    rule_id: str,
    hypothesis: str = "",
    backend: str = "auto",
) -> str:
    """Run a one-off LLM-authored CodeQL query (the *hypothesis* stage).

    Use sparingly, after the taxonomy pass, when a finding suggests a
    follow-up the templates don't cover. The query must:
    - Be valid CodeQL for the named language.
    - Include `@id ${rule_id}` (or the literal rule_id) in its preamble.
    - Use a `select X, "kind=...|...|..."`-style KV-encoded message so
      results parse identically to taxonomy templates.

    Args:
        repo_path: Repository root (must match the fingerprint).
        language: 'java' | 'cpp' | 'python'.
        query_text: The .ql source. Must compile.
        rule_id: Unique rule id for parsing — pick something namespaced
            like 'aco/<benchmark>/hypothesis-<n>'.
        hypothesis: Free-text description of what you're testing.
            Recorded in the report for traceability.
        backend: 'auto' | 'local' | 'docker'.

    Returns:
        JSON: { findings: [...], record: { hypothesis, rule_id,
        findings_count, compiled, error? } }.
    """
    findings, record = run_custom_query(
        repo_path=repo_path,
        query_text=query_text,
        rule_id=rule_id,
        language=language,
        hypothesis=hypothesis,
        backend=backend,
    )
    return json.dumps(
        {
            "findings": [f.model_dump() for f in findings],
            "record": record.model_dump(),
        },
        indent=2,
    )
