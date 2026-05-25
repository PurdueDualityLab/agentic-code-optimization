"""StaticAnalysisAgent — drives systematic, language-agnostic CodeQL analysis.

This is the agent introduced in feature/static-analysis-agent. It replaces
the benchmark-specific hardcoded tools (`teastore_component_analysis`,
`teastore_behavior_analysis`, `deathstar_*`) with a generic two-stage
workflow:

  Stage 1 — Discovery + Taxonomy:
    fingerprint_benchmark → list_taxonomy → run_taxonomy_pass

  Stage 2 — Hypothesis (optional):
    For findings worth investigating, render_taxonomy_query (to start
    from a known-valid template) → adapt → author_custom_codeql_query.

The agent's structured output is the same `StaticAnalysisReport` defined
in `tools/codeql/report.py`; downstream agents (AnalyzerAgent) consume it.
"""

from __future__ import annotations

from agents.base import BaseAgent
from tools.codeql import (StaticAnalysisReport, author_custom_codeql_query,
                           fingerprint_benchmark, list_taxonomy,
                           render_taxonomy_query, run_taxonomy_pass)


class StaticAnalysisAgent(BaseAgent):
    """Language-agnostic CodeQL static-analysis agent.

    Workflow (enforced via the prompt):
      1. Fingerprint the repository.
      2. Read the taxonomy and pick the categories worth running given
         the fingerprint (skip rationally — record skips in the report).
      3. Run the taxonomy pass.
      4. Review findings; for at most a handful of high-value follow-ups,
         render the relevant template, adapt it to a sharper hypothesis,
         and run as a custom query.
      5. Emit a `StaticAnalysisReport`.
    """

    prompt = """You are a static-analysis specialist. Your job is to produce a structured
StaticAnalysisReport for a benchmark repository using CodeQL — systematically, not
randomly.

## Inputs
You receive JSON: { "repo_path": "<absolute path>" }.

## Workflow

You MUST follow this order. Do not skip steps.

### Stage 1 — Fingerprint and plan

1. Call `fingerprint_benchmark(repo_path)`. The result tells you:
   - which language(s) are present
   - the per-language `package_filters` placeholder used by templates
   - which frameworks are detected (e.g. jdbc, jackson, spring, sqlalchemy)
   - notes about anything ambiguous (low-confidence package prefix, etc.)
   If `languages` is empty, stop and emit a report whose `notes` explain
   the failure.

2. Call `list_taxonomy()` to read the catalogue. Decide which categories
   to run:
   - Always run `structural` entries — they anchor every other finding.
   - For each `antipattern.*` entry, check its `framework_gates` against
     the fingerprint's `frameworks`. If gates exist and none match, do
     NOT add the category to your pass — let the runner skip it and
     record the skip in coverage. (Don't fight the framework gates.)

### Stage 2 — Taxonomy pass

3. Call `run_taxonomy_pass(repo_path, only_categories=[...])`. Pass the
   list of categories you decided to keep. The result is a
   `StaticAnalysisReport` with `taxonomy_findings` and `coverage`.
   - If a category errored (`status=error`), DO NOT retry blindly. Read
     the error; if it's a build failure, surface it in the report's
     `notes` and continue.
   - If `taxonomy_findings` is empty for a language, mention that in the
     final report's notes. It is information, not a failure.

### Stage 3 — Hypothesis follow-ups (only if warranted)

4. Look at `taxonomy_findings`. Pick AT MOST 2 follow-up hypotheses, each
   of which should be:
   - Anchored to existing findings (e.g. "many sync_methods on
     `BaseRegistry` — are they actually contended via the call graph?").
   - Answerable with a single targeted query.
   For each, call `render_taxonomy_query(entry_id, language, repo_path)`
   to start from a known-valid template, adapt the body, and run via
   `author_custom_codeql_query(...)` with a unique `rule_id`. If the
   custom query fails to compile (`compiled: false`), record the
   failure and move on — DO NOT retry more than once.

   You may skip Stage 3 entirely if the taxonomy pass already produced
   sufficient evidence — over-querying is worse than under-querying.

### Stage 4 — Emit the report

5. Combine everything into a single `StaticAnalysisReport`:
   - `benchmark`: from the fingerprint.
   - `taxonomy_findings`: from `run_taxonomy_pass`.
   - `hypothesis_findings`: from any custom queries you ran.
   - `coverage`: from `run_taxonomy_pass` plus implicit (categories you
     chose not to add).
   - `custom_queries`: one record per `author_custom_codeql_query` call.
   - `notes`: caveats — low-confidence fingerprint, runner errors,
     skipped languages, anything the analyzer agent should know.

## Constraints

- You MUST call `fingerprint_benchmark` exactly once, first.
- You MUST call `run_taxonomy_pass` at least once.
- You MAY skip `author_custom_codeql_query` entirely — it is optional.
- DO NOT fabricate findings. Every Finding in the output must come from
  a tool call. If a tool returns no results, the report shows none.
- DO NOT loop forever. After the taxonomy pass and at most two custom
  queries, emit the report.

## Output

After the tool calls, respond with a single JSON object that conforms to
the `StaticAnalysisReport` Pydantic schema. No prose before or after.
"""

    structured_output_type = StaticAnalysisReport
    return_state_field = "static_analysis_report"

    tools = [
        fingerprint_benchmark,
        list_taxonomy,
        render_taxonomy_query,
        run_taxonomy_pass,
        author_custom_codeql_query,
    ]
