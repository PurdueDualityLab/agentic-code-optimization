"""CodeQL execution backend — language-agnostic, with Docker fallback.

This is the only module that shells out. Two execution paths:

1. **Local CLI** — preferred when the host has the `codeql` binary on PATH
   and a database is already built. Fast, supports running individual
   query files against a cached DB. Used for taxonomy passes after the
   first one in a session, and for LLM-authored hypothesis queries.

2. **Docker (`codeql-agent` image)** — used when no local CLI is available
   or no database has been built yet. This matches the existing
   `tools/codeql.py` behaviour (mounts repo, runs `mvn clean compile`,
   then a query suite). Heavier — only used as a fallback or for the
   first build.

A small file-based build lock prevents two concurrent invocations from
clobbering Maven's build directory in the same repo. Carried over from
the original `codeql.py`.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tools.codeql.fingerprint import BenchmarkFingerprint
from tools.codeql.languages import get_adapter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lockfile (carried over from tools/codeql.py with minor cleanup)
# ---------------------------------------------------------------------------


def _acquire_build_lock(
    repo_path: Path, timeout: int = 600, poll_interval: int = 5
) -> Path:
    lock_file = repo_path / ".codeql-build.lock"
    start = time.time()
    waited = False
    while True:
        try:
            lock_file.touch(exist_ok=False)
            lock_file.write_text(
                json.dumps(
                    {"pid": os.getpid(), "timestamp": time.time()}, indent=2
                )
            )
            if waited:
                logger.info(
                    f"Build lock acquired after {time.time() - start:.1f}s"
                )
            return lock_file
        except FileExistsError:
            if not waited:
                logger.info(f"Build lock held; waiting on {lock_file}")
                waited = True
            if time.time() - start > timeout:
                # Treat very stale locks as abandoned
                try:
                    info = json.loads(lock_file.read_text())
                    age = time.time() - info.get("timestamp", time.time())
                    if age > timeout:
                        logger.warning(
                            f"Stale lock ({age:.0f}s) — removing and retrying"
                        )
                        lock_file.unlink(missing_ok=True)
                        continue
                except Exception:
                    pass
                raise TimeoutError(
                    f"Could not acquire build lock after {timeout}s: {lock_file}"
                )
            time.sleep(poll_interval)


def _release_build_lock(lock_file: Path) -> None:
    try:
        if lock_file.exists():
            lock_file.unlink()
    except Exception as e:
        logger.warning(f"Lock release failed: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class RunResult:
    """Output of a single CodeQL run.

    Findings are SARIF results parsed and grouped by rule_id, with the
    KV-encoded message text broken out into a properties dict per finding.
    """

    success: bool
    findings_by_rule: dict[str, list[dict]] = field(default_factory=dict)
    sarif_path: Optional[str] = None
    error: Optional[str] = None
    backend: str = "unknown"  # 'local' | 'docker'

    @property
    def total_findings(self) -> int:
        return sum(len(rs) for rs in self.findings_by_rule.values())


def _have_local_codeql() -> bool:
    """Check whether the `codeql` CLI is on PATH."""
    return shutil.which("codeql") is not None


def _have_docker_image(image: str = "codeql-agent") -> bool:
    """Cheap check that the codeql-agent image is available."""
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# SARIF parsing (carried over with deduplication)
# ---------------------------------------------------------------------------


def _parse_kv_message(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not text:
        return out
    for chunk in text.split("|"):
        if "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        if k:
            out[k] = v
    return out


def _parse_sarif(sarif_path: Path, rule_ids: list[str]) -> dict[str, list[dict]]:
    """Parse SARIF and return findings grouped by rule_id, deduplicated."""
    with open(sarif_path) as f:
        data = json.load(f)

    by_rule: dict[str, list[dict]] = {rid: [] for rid in rule_ids}
    seen: dict[str, set[str]] = {rid: set() for rid in rule_ids}

    for run in data.get("runs", []):
        for result in run.get("results", []):
            rid = result.get("ruleId", "")
            if rid not in by_rule:
                continue
            msg = result.get("message", {}).get("text", "")
            parsed = _parse_kv_message(msg)
            if not parsed:
                continue
            # Best-effort location info
            locs = result.get("locations", [])
            if locs:
                phys = locs[0].get("physicalLocation", {})
                art = phys.get("artifactLocation", {}).get("uri", "")
                region = phys.get("region", {})
                start_line = region.get("startLine")
                if art:
                    parsed.setdefault("file", art)
                if start_line is not None:
                    parsed.setdefault("line", str(start_line))

            dedup = "|".join(
                f"{k}={v}"
                for k, v in sorted(parsed.items())
                if k not in {"file", "line"}
            )
            if dedup in seen[rid]:
                continue
            seen[rid].add(dedup)
            by_rule[rid].append(parsed)
    return by_rule


# ---------------------------------------------------------------------------
# Docker backend (slower; rebuilds DB each run via Maven)
# ---------------------------------------------------------------------------


def _create_query_workspace(
    repo: Path, rendered_queries: dict[str, tuple[str, str]], language: str
) -> Path:
    """Lay out a CodeQL query pack inside the repo and return its path.

    `rendered_queries` maps filename → (query_text, rule_id).
    """
    from tools.codeql.render import render_qlpack

    workspace = repo / f"codeql-queries-aco-{language}"
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)
    workspace.mkdir(parents=True, exist_ok=True)

    rule_ids: list[str] = []
    for fname, (text, rid) in rendered_queries.items():
        (workspace / fname).write_text(text, encoding="utf-8")
        rule_ids.append(rid)

    suite_text = (
        "- description: ACO Static Analysis Suite\n"
        "- queries: .\n"
        "- include:\n"
        "    id:\n"
        + "".join(f"      - {r}\n" for r in rule_ids)
    )
    (workspace / "aco-suite.qls").write_text(suite_text, encoding="utf-8")
    (workspace / "qlpack.yml").write_text(render_qlpack(language), encoding="utf-8")

    return workspace


def _run_docker(
    repo: Path,
    workspace: Path,
    language: str,
    build_command: str,
) -> Path:
    """Invoke the codeql-agent Docker image. Returns SARIF path."""
    container = f"codeql-aco-{language}"
    results_dir_name = f"codeql-aco-results-{language}"

    docker_cmd = [
        "docker", "run", "--rm",
        "--name", container,
        "-v", f"{repo}:/opt/src",
        "-v", f"{repo / results_dir_name}:/opt/results",
        "-e", f"LANGUAGE={language}",
        "-e", f"COMMAND={build_command}",
        "-e", f"QS=/opt/src/{workspace.name}/aco-suite.qls",
        "codeql-agent",
    ]
    logger.info(f"Running CodeQL via Docker: {' '.join(docker_cmd)}")

    process = subprocess.Popen(
        docker_cmd,
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    output_tail: list[str] = []
    if process.stdout:
        for line in process.stdout:
            line = line.rstrip()
            output_tail.append(line)
            if len(output_tail) > 200:
                output_tail = output_tail[-200:]
            logger.debug(f"docker: {line}")
    rc = process.wait()
    if rc != 0:
        raise RuntimeError(
            f"CodeQL Docker run failed (exit {rc}):\n"
            + "\n".join(output_tail[-30:])
        )
    sarif = repo / results_dir_name / "issues.sarif"
    if not sarif.exists():
        raise RuntimeError(f"SARIF results missing at {sarif}")
    return sarif


_DEFAULT_BUILD_COMMANDS: dict[str, str] = {
    "java": "mvn clean compile -DskipTests -Dmaven.repo.local=/opt/src/build-local",
    "cpp": "make",  # Often overridden — DeathStarBench uses CMake
    "python": "echo 'no build'",  # Python doesn't need build
}


# ---------------------------------------------------------------------------
# Local CLI backend (fast; uses pre-built DB)
# ---------------------------------------------------------------------------


def _ensure_local_database(
    repo: Path, language: str, db_root: Path, build_command: Optional[str] = None
) -> Path:
    """Create a CodeQL database under db_root if not already present."""
    adapter = get_adapter(language)
    if adapter is None:
        raise RuntimeError(f"Unknown language: {language}")
    db_path = db_root / f"db-{language}"
    if db_path.exists() and (db_path / "codeql-database.yml").exists():
        logger.info(f"Reusing existing CodeQL DB at {db_path}")
        return db_path

    db_root.mkdir(parents=True, exist_ok=True)
    cmd = [
        "codeql", "database", "create",
        str(db_path),
        f"--language={adapter.codeql_language}",
        "--source-root", str(repo),
        "--overwrite",
    ]
    if build_command:
        cmd += ["--command", build_command]
    logger.info(f"Building CodeQL DB: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        raise RuntimeError(
            f"codeql database create failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout[-800:]}\nstderr: {result.stderr[-800:]}"
        )
    return db_path


def _run_local_suite(db_path: Path, workspace: Path) -> Path:
    """Run a query suite against an existing DB via local codeql CLI."""
    import os
    env = os.environ.copy()
    env["CODEQL_ALLOW_INSTALLATION_ANYWHERE"] = "true"
    # Install packs before analyzing
    pack_cmd = ["codeql", "pack", "install", str(workspace)]
    logger.info(f"Installing CodeQL packs: {' '.join(pack_cmd)}")
    pack_result = subprocess.run(pack_cmd, capture_output=True, text=True, timeout=300, env=env)
    if pack_result.returncode != 0:
        logger.warning(f"codeql pack install warning: {pack_result.stderr[-400:]}")
    sarif = workspace / "issues.sarif"
    cmd = [
        "codeql", "database", "analyze",
        str(db_path),
        str(workspace / "aco-suite.qls"),
        "--format=sarif-latest",
        "--output", str(sarif),
    ]
    logger.info(f"Running CodeQL suite locally: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, env=env)
    if result.returncode != 0:
        logger.warning(
            f"codeql database analyze failed (exit {result.returncode}), "
            f"skipping language. stderr: {result.stderr[-400:]}"
        )
        # Write empty SARIF so callers don't crash
        empty_sarif = '{"version":"2.1.0","runs":[]}'
        sarif.write_text(empty_sarif, encoding="utf-8")
    return sarif


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def run_rendered_queries(
    repo_path: str | Path,
    rendered_queries: dict[str, tuple[str, str]],
    language: str,
    fingerprint: Optional[BenchmarkFingerprint] = None,
    build_command: Optional[str] = None,
    prefer: str = "auto",
) -> RunResult:
    """Run a batch of pre-rendered queries against `repo_path`.

    Args:
        repo_path: Repository root.
        rendered_queries: filename → (query_text, rule_id). Filename only
            matters as the on-disk artefact name; rule_ids drive parsing.
        language: Language id (matches the adapter / fingerprint key).
        fingerprint: Optional — only used to override default build cmd.
        build_command: Override the language default build command.
        prefer: 'auto' | 'local' | 'docker'. 'auto' picks local if codeql
            CLI is on PATH, otherwise docker.

    Returns:
        RunResult with deduplicated findings grouped by rule_id.
    """
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        return RunResult(success=False, error=f"Not a directory: {repo}")

    if not rendered_queries:
        return RunResult(success=True, findings_by_rule={})

    rule_ids = [rid for (_, rid) in rendered_queries.values()]
    workspace = _create_query_workspace(repo, rendered_queries, language)

    backend = prefer
    if backend == "auto":
        backend = "local" if _have_local_codeql() else "docker"

    lock_file = _acquire_build_lock(repo)
    try:
        if backend == "local":
            db_root = repo / "codeql-db-aco"
            db_path = _ensure_local_database(
                repo, language, db_root,
                build_command=build_command or _DEFAULT_BUILD_COMMANDS.get(language),
            )
            sarif = _run_local_suite(db_path, workspace)
        else:
            if not _have_docker_image():
                return RunResult(
                    success=False,
                    error=(
                        "No local codeql CLI on PATH and codeql-agent Docker "
                        "image not available. Install one of them."
                    ),
                    backend=backend,
                )
            sarif = _run_docker(
                repo,
                workspace,
                language,
                build_command or _DEFAULT_BUILD_COMMANDS.get(language, "echo nobuild"),
            )
        findings = _parse_sarif(sarif, rule_ids)
        return RunResult(
            success=True,
            findings_by_rule=findings,
            sarif_path=str(sarif),
            backend=backend,
        )
    except Exception as e:
        logger.error(f"CodeQL run failed: {e}", exc_info=True)
        return RunResult(success=False, error=str(e), backend=backend)
    finally:
        _release_build_lock(lock_file)
        # Clean up the per-run workspace; keep db for reuse on local backend
        try:
            shutil.rmtree(workspace, ignore_errors=True)
        except Exception:
            pass
