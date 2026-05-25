"""High-level orchestration: render → execute → emit `Finding` records.

This sits between the low-level `runner` (which knows about SARIF and
Docker) and the `@tool` wrappers (which expose JSON to the LLM). It is
the place where a single "taxonomy pass" is materialised: pick the
applicable entries for each language in the fingerprint, render them,
batch them by language, run them, and parse results back into
`Finding` records that can be embedded in the `StaticAnalysisReport`.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

from tools.codeql.fingerprint import (BenchmarkFingerprint,
                                       fingerprint_repository)
from tools.codeql.render import (TemplateRenderError, render_qlpack,
                                  render_query)
from tools.codeql.report import (BenchmarkSummary, CustomQueryRecord, Finding,
                                  StaticAnalysisReport, TaxonomyCoverage)
from tools.codeql.runner import RunResult, run_rendered_queries
from tools.codeql.taxonomy import TAXONOMY, TaxonomyEntry, get_entry

logger = logging.getLogger(__name__)


def _findings_from_run(
    run: RunResult,
    rule_id_to_entry: dict[str, TaxonomyEntry],
    language: str,
) -> list[Finding]:
    findings: list[Finding] = []
    for rule_id, results in run.findings_by_rule.items():
        entry = rule_id_to_entry.get(rule_id)
        category = entry.category if entry else "unknown"
        entry_id = entry.id if entry else "custom"
        for parsed in results:
            location = (
                parsed.get("fqn")
                or parsed.get("in_method")
                or parsed.get("in_function")
                or parsed.get("class")
                or parsed.get("file")
                or "<unknown>"
            )
            evidence = "|".join(
                f"{k}={v}" for k, v in sorted(parsed.items()) if k != "kind"
            )
            findings.append(
                Finding(
                    rule_id=rule_id,
                    category=category,
                    taxonomy_entry=entry_id,
                    language=language,
                    location=location,
                    evidence=evidence,
                    severity="info",
                    properties=parsed,
                )
            )
    return findings


def run_taxonomy(
    repo_path: str,
    fingerprint: Optional[BenchmarkFingerprint] = None,
    only_categories: Optional[list[str]] = None,
    only_languages: Optional[list[str]] = None,
    backend: str = "auto",
) -> StaticAnalysisReport:
    """Execute the systematic taxonomy pass.

    Args:
        repo_path: Repository root.
        fingerprint: Optional pre-computed fingerprint. If omitted we
            compute one — but callers usually pass it because the agent
            inspects it before the pass.
        only_categories: Restrict to a subset of taxonomy categories
            (e.g. ['structural', 'concurrency']).
        only_languages: Restrict to a subset of detected languages.
        backend: Forwarded to the runner ('auto'|'local'|'docker').

    Returns:
        Populated `StaticAnalysisReport` (taxonomy_findings + coverage,
        no hypothesis findings).
    """
    fp = fingerprint or fingerprint_repository(repo_path)

    summary = BenchmarkSummary(
        repo_path=fp.repo_path,
        languages=fp.languages,
        primary_language=fp.primary_language,
        package_filters=fp.package_filters,
        frameworks=sorted({fw for fws in fp.frameworks.values() for fw in fws}),
        build_systems=fp.build_systems,
    )
    report = StaticAnalysisReport(benchmark=summary)
    report.notes.extend(fp.notes)

    if not fp.languages:
        report.notes.append(
            "No supported languages detected — taxonomy pass skipped."
        )
        return report

    target_languages = (
        [l for l in fp.languages if l in only_languages]
        if only_languages
        else fp.languages
    )

    # Group rendered queries by language so we run the runner once per language.
    rendered_by_language: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    rule_id_to_entry: dict[str, TaxonomyEntry] = {}

    for entry in TAXONOMY:
        if only_categories and entry.category not in only_categories:
            continue
        for language in target_languages:
            applicable, reason = entry.applicable_to(language, fp)
            if not applicable:
                report.coverage.append(
                    TaxonomyCoverage(
                        entry_id=entry.id,
                        language=language,
                        status="skipped",
                        skip_reason=reason,
                    )
                )
                continue
            try:
                query_text, rule_id = render_query(entry, language, fp)
            except TemplateRenderError as e:
                report.coverage.append(
                    TaxonomyCoverage(
                        entry_id=entry.id,
                        language=language,
                        status="error",
                        error=str(e),
                    )
                )
                logger.warning(f"Template render failed for {entry.id}/{language}: {e}")
                continue
            # Use the rule_id as the file stem so collisions can't happen.
            stem = rule_id.replace("/", "__")
            rendered_by_language[language][f"{stem}.ql"] = (query_text, rule_id)
            rule_id_to_entry[rule_id] = entry

    # Execute per-language batches
    for language, queries in rendered_by_language.items():
        if not queries:
            continue
        run = run_rendered_queries(
            repo_path=repo_path,
            rendered_queries=queries,
            language=language,
            fingerprint=fp,
            prefer=backend,
        )
        if not run.success:
            for fname, (_, rule_id) in queries.items():
                entry = rule_id_to_entry.get(rule_id)
                report.coverage.append(
                    TaxonomyCoverage(
                        entry_id=entry.id if entry else "unknown",
                        language=language,
                        status="error",
                        error=run.error or "unknown runner failure",
                    )
                )
            report.notes.append(
                f"CodeQL runner failed for {language} ({run.backend}): {run.error}"
            )
            continue

        # Mark every rule that ran (whether or not it produced findings)
        for fname, (_, rule_id) in queries.items():
            entry = rule_id_to_entry.get(rule_id)
            if not entry:
                continue
            n = len(run.findings_by_rule.get(rule_id, []))
            report.coverage.append(
                TaxonomyCoverage(
                    entry_id=entry.id,
                    language=language,
                    status="run",
                    findings_count=n,
                )
            )

        report.taxonomy_findings.extend(
            _findings_from_run(run, rule_id_to_entry, language)
        )

    return report


def run_custom_query(
    repo_path: str,
    query_text: str,
    rule_id: str,
    language: str,
    hypothesis: str = "",
    fingerprint: Optional[BenchmarkFingerprint] = None,
    backend: str = "auto",
) -> tuple[list[Finding], CustomQueryRecord]:
    """Run a one-off LLM-authored query against the repo.

    Used for the hypothesis stage. The query body must already include a
    `@id` matching `rule_id`.
    """
    fp = fingerprint or fingerprint_repository(repo_path)
    queries = {f"custom_{rule_id.replace('/', '__')}.ql": (query_text, rule_id)}
    run = run_rendered_queries(
        repo_path=repo_path,
        rendered_queries=queries,
        language=language,
        fingerprint=fp,
        prefer=backend,
    )
    if not run.success:
        return [], CustomQueryRecord(
            hypothesis=hypothesis,
            language=language,
            query_text=query_text,
            rule_id=rule_id,
            findings_count=0,
            compiled=False,
            error=run.error,
        )
    findings = _findings_from_run(run, {}, language)
    record = CustomQueryRecord(
        hypothesis=hypothesis,
        language=language,
        query_text=query_text,
        rule_id=rule_id,
        findings_count=len(findings),
        compiled=True,
    )
    return findings, record
