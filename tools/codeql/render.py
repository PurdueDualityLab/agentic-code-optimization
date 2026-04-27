"""Render taxonomy templates into concrete CodeQL query text.

The substitution is intentionally simple: we use Python's `string.Template`
(the `${VAR}` form) so templates remain valid CodeQL when viewed standalone
(every placeholder maps to either a string-literal context or a regex
context inside the .ql, never to QL syntax itself).

We deliberately do *not* use Jinja2 or any heavier templating engine —
this keeps templates readable to anyone who knows CodeQL, and avoids a
runtime dep. The renderer is pure data-in / data-out, so it's trivial to
unit test.
"""

from __future__ import annotations

import logging
from pathlib import Path
from string import Template

from tools.codeql.fingerprint import BenchmarkFingerprint
from tools.codeql.languages import get_adapter
from tools.codeql.taxonomy import TaxonomyEntry, get_entry

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class TemplateRenderError(RuntimeError):
    """Raised when a template can't be loaded or substituted."""


def _load_template(rel_path: str) -> str:
    """Load a template file by its taxonomy-relative path."""
    full = _TEMPLATES_DIR / rel_path
    if not full.is_file():
        raise TemplateRenderError(f"Template file missing: {full}")
    return full.read_text(encoding="utf-8")


def render_query(
    entry: TaxonomyEntry, language: str, fingerprint: BenchmarkFingerprint
) -> tuple[str, str]:
    """Render the .ql text for `entry` in `language` against `fingerprint`.

    Returns:
        (query_text, rule_id) — the rule_id is also injected into the
        query body so that SARIF results can be parsed back to the
        originating taxonomy entry.

    Raises:
        TemplateRenderError on missing template or unmet placeholder.
    """
    rel_path = entry.templates.get(language)
    if not rel_path:
        raise TemplateRenderError(
            f"Taxonomy entry {entry.id} has no template for language={language}"
        )
    adapter = get_adapter(language)
    if adapter is None:
        raise TemplateRenderError(f"Unknown language: {language}")

    raw = _load_template(rel_path)
    params = adapter.extract_params(fingerprint)

    rule_id_template = Template(entry.rule_id_format)
    try:
        rule_id = rule_id_template.substitute(params)
    except KeyError as e:
        raise TemplateRenderError(
            f"rule_id_format {entry.rule_id_format!r} requires placeholder {e.args[0]} "
            f"which the {language} adapter did not supply"
        ) from e

    params_with_rule = {**params, "RULE_ID": rule_id}

    try:
        rendered = Template(raw).substitute(params_with_rule)
    except KeyError as e:
        raise TemplateRenderError(
            f"Template {rel_path} references placeholder ${{{e.args[0]}}} "
            f"which the {language} adapter did not supply. "
            f"Available: {sorted(params_with_rule.keys())}"
        ) from e
    return rendered, rule_id


def render_qlpack(language: str) -> str:
    """Render a minimal qlpack.yml for the given language."""
    adapter = get_adapter(language)
    if adapter is None:
        raise TemplateRenderError(f"Unknown language: {language}")
    deps = "\n".join(f"  - {d}" for d in adapter.qlpack_dependencies)
    name_safe = language
    return f"""name: aco/{name_safe}-analysis
version: 0.0.1
libraryPathDependencies:
{deps}
"""


def render_by_id(
    entry_id: str, language: str, fingerprint: BenchmarkFingerprint
) -> tuple[str, str]:
    """Convenience: look up the entry by id, then render."""
    entry = get_entry(entry_id)
    if entry is None:
        raise TemplateRenderError(f"Unknown taxonomy entry: {entry_id}")
    return render_query(entry, language, fingerprint)
