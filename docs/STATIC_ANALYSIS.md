# Static Analysis Agent

The `StaticAnalysisAgent` (introduced on `feature/static-analysis-agent`)
replaces the benchmark-specific hardcoded CodeQL tooling
(`tools/codeql.py` + `tools/codeql_cpp.py`) with a generic, language-agnostic
agent that runs a systematic analysis pass against any repository it is
pointed at — no per-benchmark code changes required.

## Why

Before this branch, every CodeQL query was bound to a specific benchmark.
The Java queries hardcoded `tools.descartes.teastore.%`, the C++ queries
hardcoded `socialNetwork/src/%`. Adding a new benchmark meant forking
`tools/codeql.py`, rewriting every query, and wiring a new tool into the
summarizer agents. Worse, the agents that called these tools had no
control over *what* got run — they invoked one of two opaque combined
queries blindly.

The new agent flips this around: queries are vetted templates
parameterised by a runtime fingerprint, and selection is driven by a
performance anti-pattern taxonomy.

## Pipeline placement

The agent runs as **Phase 2** in `workflows/complete_pipeline.py`:

```
START → summarization → static_analysis → analysis → optimization → correctness_check → ...
```

Its structured output (`StaticAnalysisReport`) is written into the
pipeline state under `static_analysis_report` and passed to
`AnalyzerAgent` alongside the existing summary text.

## Workflow

The agent's prompt enforces a four-stage workflow:

1. **Fingerprint.** `fingerprint_benchmark(repo_path)` runs pure
   filesystem inspection: detected languages, dominant package roots,
   framework markers, build systems. The fingerprint is the single
   source of truth for every downstream parameter.

2. **Plan.** `list_taxonomy()` returns the catalogue of analysis
   entries. The agent picks which categories to run given the
   fingerprint — gated entries (e.g. `antipattern.db_access_sites`) are
   automatically skipped when the gating framework is absent, with the
   skip reason recorded in `coverage`.

3. **Run the taxonomy.** `run_taxonomy_pass(repo_path, only_categories)`
   renders every applicable template, batches by language, executes via
   the CodeQL runner (local CLI if available, Docker otherwise), and
   parses SARIF into `Finding` records.

4. **Hypothesise (optional).** Up to two LLM-authored follow-up queries
   via `author_custom_codeql_query`, each starting from a known-valid
   template (`render_taxonomy_query`). Useful when a taxonomy finding
   suggests a sharper question (e.g. "are these synchronised methods
   actually called from the hot path?").

The agent then emits a `StaticAnalysisReport` whose schema is in
`tools/codeql/report.py`.

## Taxonomy

The analysis taxonomy lives in `tools/codeql/taxonomy.py`. Entries are
grouped into two stages:

**Stage 1 — Structural backbone**

| Entry | Description |
|---|---|
| `structural.services` | Service-like classes / components |
| `structural.endpoints` | Externally reachable entry points |
| `structural.call_graph` | Class/function-level call edges |

**Stage 2 — Anti-pattern probes**

| Entry | Category | Languages | Framework gates |
|---|---|---|---|
| `antipattern.synchronization` | concurrency | java, cpp, python | — |
| `antipattern.http_client_construction` | io | java, python | java: okhttp / apache-httpclient / spring; python: requests / aiohttp / fastapi / flask |
| `antipattern.serialization_per_request` | io | java | jackson / gson |
| `antipattern.string_concat_in_loop` | allocation | java, python | — |
| `antipattern.db_access_sites` | database | java, python | java: jdbc / jpa / hibernate; python: sqlalchemy / django |
| `antipattern.logging_in_hot_path` | logging | java, python | java: log4j |

## Extending

### Add a new template for an existing taxonomy entry / language

1. Drop a `.ql` file under
   `tools/codeql/templates/<lang>/<stage>/<name>.ql`.
2. Use the placeholders advertised by the language adapter
   (`tools/codeql/languages/<lang>.py`):
   - Java: `${PACKAGE_LIKE}`, `${PACKAGE_PREFIX}`, `${PACKAGE_REGEX_CAPTURE}`
   - C++ / Python: `${PATH_LIKE}`, `${PATH_REGEX_CAPTURE}`
   - All: `${RULE_ID}`, `${RULE_PREFIX}`
3. Reference it in a `TaxonomyEntry.templates` mapping.

### Add a new language

1. Create `tools/codeql/languages/<lang>.py` exporting a
   `LanguageAdapter` whose `param_extractor(fingerprint)` returns the
   placeholder dict your templates use.
2. Register it in `LANGUAGE_ADAPTERS` in
   `tools/codeql/languages/__init__.py`.
3. Add `<lang>` to the `_LANG_EXTS` and (optionally)
   `_FRAMEWORK_MARKERS` dicts in `tools/codeql/fingerprint.py`.
4. Drop templates under `tools/codeql/templates/<lang>/...` and add the
   language to applicable `TaxonomyEntry.languages` sets.

### Add a new taxonomy entry

Append a `TaxonomyEntry(...)` to `TAXONOMY` in
`tools/codeql/taxonomy.py`. Set `framework_gates` to skip noise on
benchmarks that obviously don't apply.

## Backwards compatibility

`tools/codeql.py` and `tools/codeql_cpp.py` remain in the codebase and
the `ComponentSummarizerAgent` / `BehaviorSummarizerAgent` continue to
import from them. They are now redundant with the
`StaticAnalysisAgent`'s output but were left in place to avoid breaking
existing runs. A follow-up branch can delete them and have the
summarisers consume the StaticAnalysisReport instead.

## Verifying

The render layer is testable without a CodeQL install. Stub a
`BenchmarkFingerprint` and call `render_query(entry, language, fp)` —
every placeholder must substitute. There is a self-test pattern in the
verification scripts used while developing this branch (see
`/tmp/test_render.py` style — applied in CI is left as a follow-up).
