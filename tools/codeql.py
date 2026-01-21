"""CodeQL analysis tools for TeaStore benchmarks.

NOTE: This module contains hardcoded tools specifically designed for TeaStore microservices architecture.
These tools are not generic and should only be used with TeaStore benchmark repositories.
"""

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ============================================================================
# CODEQL QUERY FILE TEMPLATES
# ============================================================================

FIND_MICROSERVICES_QUERY = """/**
 * @name Identify TeaStore Microservices (Simple)
 * @description Finds microservices by analyzing package structure
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/find-microservices-simple
 */

import java

/**
 * Extract microservice name from package
 */
string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\\\.descartes\\\\.teastore\\\\.([^.]+).*", 1)
  )
}

/**
 * Check if a class is a significant microservice component
 */
predicate isSignificantComponent(Class c) {
  c.getName().matches("%Servlet") or
  c.getName().matches("%Endpoint") or
  c.getName().matches("%Rest") or
  c.getName().matches("%Service") or
  c.getName().matches("%Application") or
  c.getName().matches("%Registry") or
  c.getPackage().getName().matches("%.rest") or
  c.getPackage().getName().matches("%.servlet")
}

from Class c, string serviceName
where
  serviceName = getMicroserviceFromPackage(c.getPackage()) and
  isSignificantComponent(c) and
  c.fromSource()
select c, "kind=microservice|service=" + serviceName + "|component_fqn=" + c.getQualifiedName() +
  "|file=" + c.getLocation().getFile().getRelativePath() +
  "|start_line=" + c.getLocation().getStartLine() +
  "|end_line=" + c.getLocation().getEndLine()
"""

FIND_ENDPOINTS_QUERY = """/**
 * @name Find All Endpoints (Ultra Simple)
 * @description Finds all classes that look like endpoints based on naming only
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/find-all-endpoints
 */

import java

/**
 * Get the microservice name from package
 */
string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\\\.descartes\\\\.teastore\\\\.([^.]+).*", 1)
  )
}

from Class c, string serviceName
where
  // Class name indicates it's an endpoint
  (c.getName().matches("%Servlet") or
   c.getName().matches("%Endpoint") or
   c.getName().matches("%Rest") or
   c.getName().matches("%Controller")) and
  // In teastore package
  c.getPackage().getName().matches("tools.descartes.teastore.%") and
  serviceName = getMicroserviceFromPackage(c.getPackage()) and
  c.fromSource()
select c, "kind=endpoint|service=" + serviceName + "|endpoint_fqn=" + c.getQualifiedName() +
  "|file=" + c.getLocation().getFile().getRelativePath() +
  "|start_line=" + c.getLocation().getStartLine() +
  "|end_line=" + c.getLocation().getEndLine()
"""

COMPONENT_INVENTORY_QUERY = """/**
 * @name TeaStore Component Inventory
 * @description Lists packages, classes, and methods for each TeaStore service
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/component-inventory
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\\\.descartes\\\\.teastore\\\\.([^.]+).*", 1)
  )
}

from Package p, string serviceName
where
  serviceName = getMicroserviceFromPackage(p)
select p, "kind=component_inventory|service=" + serviceName + "|component_kind=package|component_fqn=" +
  p.getName()

from Class c, string serviceName
where
  serviceName = getMicroserviceFromPackage(c.getPackage()) and
  c.fromSource()
select c, "kind=component_inventory|service=" + serviceName + "|component_kind=class|component_fqn=" +
  c.getQualifiedName() + "|file=" + c.getLocation().getFile().getRelativePath() +
  "|start_line=" + c.getLocation().getStartLine() +
  "|end_line=" + c.getLocation().getEndLine()

from Method m, string serviceName
where
  serviceName = getMicroserviceFromPackage(m.getDeclaringType().getPackage()) and
  m.fromSource()
select m, "kind=component_inventory|service=" + serviceName + "|component_kind=method|component_fqn=" +
  m.getQualifiedName() + "|file=" + m.getLocation().getFile().getRelativePath() +
  "|start_line=" + m.getLocation().getStartLine() +
  "|end_line=" + m.getLocation().getEndLine()
"""

HIERARCHICAL_COMPOSITION_QUERY = """/**
 * @name TeaStore Hierarchical Composition
 * @description Captures package/class/method containment and inheritance
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/hierarchical-composition
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\\\.descartes\\\\.teastore\\\\.([^.]+).*", 1)
  )
}

from Package p, Class c, string serviceName
where
  c.getPackage() = p and
  serviceName = getMicroserviceFromPackage(p) and
  c.fromSource()
select c, "kind=hierarchical_composition|service=" + serviceName + "|parent_kind=package|parent_fqn=" + p.getName() +
  "|child_kind=class|child_fqn=" + c.getQualifiedName() +
  "|file=" + c.getLocation().getFile().getRelativePath() +
  "|start_line=" + c.getLocation().getStartLine() +
  "|end_line=" + c.getLocation().getEndLine()

from Class c, Method m, string serviceName
where
  m.getDeclaringType() = c and
  serviceName = getMicroserviceFromPackage(c.getPackage()) and
  m.fromSource()
select m, "kind=hierarchical_composition|service=" + serviceName + "|parent_kind=class|parent_fqn=" + c.getQualifiedName() +
  "|child_kind=method|child_fqn=" + m.getQualifiedName() +
  "|file=" + m.getLocation().getFile().getRelativePath() +
  "|start_line=" + m.getLocation().getStartLine() +
  "|end_line=" + m.getLocation().getEndLine()

from Class sub, Class sup, string serviceName
where
  sub.fromSource() and
  sup = sub.getSuperclass() and
  serviceName = getMicroserviceFromPackage(sub.getPackage())
select sub, "kind=hierarchical_composition|service=" + serviceName + "|parent_kind=class|parent_fqn=" + sup.getQualifiedName() +
  "|child_kind=class|child_fqn=" + sub.getQualifiedName() +
  "|file=" + sub.getLocation().getFile().getRelativePath() +
  "|start_line=" + sub.getLocation().getStartLine() +
  "|end_line=" + sub.getLocation().getEndLine()
"""

EXPORTED_HTTP_ENDPOINTS_QUERY = """/**
 * @name TeaStore Exported HTTP Endpoints
 * @description Captures endpoint-like classes by naming conventions
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/exported-http-endpoints
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\\\.descartes\\\\.teastore\\\\.([^.]+).*", 1)
  )
}

from Class c, string serviceName
where
  serviceName = getMicroserviceFromPackage(c.getPackage()) and
  (c.getName().matches("%Endpoint") or c.getName().matches("%Rest") or
   c.getPackage().getName().matches("%.rest")) and
  c.fromSource()
select c, "kind=exported_http_endpoint|service=" + serviceName + "|endpoint_fqn=" + c.getQualifiedName() +
  "|file=" + c.getLocation().getFile().getRelativePath() +
  "|start_line=" + c.getLocation().getStartLine() +
  "|end_line=" + c.getLocation().getEndLine()
"""

EXPORTED_PUBLIC_API_QUERY = """/**
 * @name TeaStore Exported Public API
 * @description Captures public methods exposed by services
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/exported-public-api
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\\\.descartes\\\\.teastore\\\\.([^.]+).*", 1)
  )
}

from Method m, string serviceName
where
  m.isPublic() and
  serviceName = getMicroserviceFromPackage(m.getDeclaringType().getPackage()) and
  m.fromSource()
select m, "kind=exported_public_api|service=" + serviceName + "|method_fqn=" + m.getQualifiedName() +
  "|file=" + m.getLocation().getFile().getRelativePath() +
  "|start_line=" + m.getLocation().getStartLine() +
  "|end_line=" + m.getLocation().getEndLine()
"""

DEPS_CALL_BASED_QUERY = """/**
 * @name TeaStore Call-Based Dependencies
 * @description Captures method call edges
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/deps-call-based
 */

import java

from MethodCall call
where
  call.getEnclosingCallable().getDeclaringType().getPackage().getName().matches("tools.descartes.teastore.%") and
  call.getTarget().getDeclaringType().getPackage().getName().matches("tools.descartes.teastore.%")
select call, "kind=deps_call_based|caller=" + call.getEnclosingCallable().getQualifiedName() +
  "|callee=" + call.getTarget().getQualifiedName() +
  "|file=" + call.getLocation().getFile().getRelativePath() +
  "|start_line=" + call.getLocation().getStartLine() +
  "|end_line=" + call.getLocation().getEndLine()
"""

DEPS_TYPE_BASED_QUERY = """/**
 * @name TeaStore Type-Based Dependencies
 * @description Captures type references in TeaStore packages
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/deps-type-based
 */

import java

from TypeAccess ta
where
  ta.getEnclosingCallable().getDeclaringType().getPackage().getName().matches("tools.descartes.teastore.%")
select ta, "kind=deps_type_based|type=" + ta.getType().getQualifiedName() +
  "|file=" + ta.getLocation().getFile().getRelativePath() +
  "|start_line=" + ta.getLocation().getStartLine() +
  "|end_line=" + ta.getLocation().getEndLine()
"""

DEPS_RESOURCE_BASED_QUERY = """/**
 * @name TeaStore Resource-Based Dependencies
 * @description Captures resource references (URLs, file paths)
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/deps-resource-based
 */

import java

from StringLiteral s
where
  s.getValue().matches("%http%") or s.getValue().matches("%/api/%")
select s, "kind=deps_resource_based|value=" + s.getValue() +
  "|file=" + s.getLocation().getFile().getRelativePath() +
  "|start_line=" + s.getLocation().getStartLine() +
  "|end_line=" + s.getLocation().getEndLine()
"""

ROOTED_CALL_GRAPH_DEPTH5_QUERY = """/**
 * @name TeaStore Rooted Call Graph Depth 5
 * @description Captures interprocedural call graph edges within TeaStore packages
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/rooted-call-graph-depth5
 */

import java

from MethodCall call
where
  call.getEnclosingCallable().getDeclaringType().getPackage().getName().matches("tools.descartes.teastore.%") and
  call.getTarget().getDeclaringType().getPackage().getName().matches("tools.descartes.teastore.%")
select call, "kind=call_graph_edge|caller=" + call.getEnclosingCallable().getQualifiedName() +
  "|callee=" + call.getTarget().getQualifiedName() +
  "|file=" + call.getLocation().getFile().getRelativePath() +
  "|start_line=" + call.getLocation().getStartLine() +
  "|end_line=" + call.getLocation().getEndLine()
"""

CONTROL_FLOW_STRUCTURE_QUERY = """/**
 * @name TeaStore Control Flow Structure
 * @description Captures control-flow statements (if/for/while/switch)
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/control-flow-structure
 */

import java

from Stmt s
where
  s instanceof IfStmt or
  s instanceof ForStmt or
  s instanceof WhileStmt or
  s instanceof SwitchStmt
select s, "kind=control_flow_structure|statement=" + s.getClass().getName() +
  "|file=" + s.getLocation().getFile().getRelativePath() +
  "|start_line=" + s.getLocation().getStartLine() +
  "|end_line=" + s.getLocation().getEndLine()
"""

INTERACTION_SITES_QUERY = """/**
 * @name TeaStore Interaction Sites
 * @description Captures external calls and database access sites
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/interaction-sites
 */

import java

predicate isDbPackage(string pkg) {
  pkg.matches("java\\\\.sql(\\\\..*)?") or
  pkg.matches("javax\\\\.sql(\\\\..*)?") or
  pkg.matches("javax\\\\.persistence(\\\\..*)?") or
  pkg.matches("org\\\\.hibernate(\\\\..*)?") or
  pkg.matches("org\\\\.springframework\\\\.jdbc(\\\\..*)?")
}

from MethodCall call
where
  call.getEnclosingCallable().getDeclaringType().getPackage().getName().matches("tools.descartes.teastore.%") and
  not call.getTarget().getDeclaringType().getPackage().getName().matches("tools.descartes.teastore.%")
select call, "kind=interaction_site|target=" + call.getTarget().getQualifiedName() +
  "|file=" + call.getLocation().getFile().getRelativePath() +
  "|start_line=" + call.getLocation().getStartLine() +
  "|end_line=" + call.getLocation().getEndLine()

from MethodCall call
where
  call.getEnclosingCallable().getDeclaringType().getPackage().getName().matches("tools.descartes.teastore.%") and
  isDbPackage(call.getTarget().getDeclaringType().getPackage().getName())
select call, "kind=db_access_site|target=" + call.getTarget().getQualifiedName() +
  "|file=" + call.getLocation().getFile().getRelativePath() +
  "|start_line=" + call.getLocation().getStartLine() +
  "|end_line=" + call.getLocation().getEndLine()
"""

SYNCHRONIZATION_CONSTRUCTS_QUERY = """/**
 * @name TeaStore Synchronization Constructs
 * @description Captures synchronized blocks and methods
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/synchronization-constructs
 */

import java

from Method m
where
  m.isSynchronized() and
  m.fromSource()
select m, "kind=synchronization_construct|type=method|method_fqn=" + m.getQualifiedName() +
  "|file=" + m.getLocation().getFile().getRelativePath() +
  "|start_line=" + m.getLocation().getStartLine() +
  "|end_line=" + m.getLocation().getEndLine()
"""

QLPACK_YML = """name: teastore/microservice-analysis
version: 0.0.1
libraryPathDependencies:
  - codeql/java-all
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _create_query_files(queries_dir: Path, query_text: str, rule_id: str) -> None:
    """Write CodeQL query files to the specified directory.

    Args:
        queries_dir: Directory where query files should be written
        query_text: CodeQL query text to write
        rule_id: Rule ID to include in the single-query suite
    """
    queries_dir.mkdir(parents=True, exist_ok=True)

    suite_text = """- description: TeaStore Single Query
- queries: .
- include:
    id:
      - {rule_id}
""".format(rule_id=rule_id)

    (queries_dir / "query.ql").write_text(query_text)
    (queries_dir / "teastore-analysis.qls").write_text(suite_text)
    (queries_dir / "qlpack.yml").write_text(QLPACK_YML)

    logger.info(f"Created CodeQL query files in {queries_dir}")


def _run_codeql_analysis(repo_path: Path) -> Path:
    """Run CodeQL analysis using Docker container.

    Args:
        repo_path: Path to the TeaStore repository

    Returns:
        Path to the SARIF results file

    Raises:
        RuntimeError: If Docker command fails
    """
    logger.info("Running CodeQL analysis via Docker...")

    # Docker command from run-analysis.sh
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "--name",
        "codeql-agent-docker",
        "-v",
        f"{repo_path}:/opt/src",
        "-v",
        f"{repo_path}/codeql-agent-results:/opt/results",
        "-e",
        "LANGUAGE=java",
        "-e",
        "COMMAND=mvn clean compile -DskipTests -pl !utilities/tools.descartes.teastore.docker.all",
        "-e",
        "QS=/opt/src/codeql-queries/teastore-analysis.qls",
        "codeql-agent",
    ]

    try:
        # Use Popen to stream output in real-time
        process = subprocess.Popen(
            docker_cmd,
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1,  # Line buffered
        )

        # Stream output line by line
        output_lines = []
        if process.stdout:
            for line in process.stdout:
                line = line.rstrip()
                print(line)  # Stream to stdout
                output_lines.append(line)
                logger.debug(f"Docker: {line}")

        # Wait for process to complete
        return_code = process.wait()

        if return_code != 0:
            error_output = "\n".join(output_lines[-20:])  # Last 20 lines
            raise RuntimeError(f"CodeQL analysis failed with exit code {return_code}:\n{error_output}")

        logger.info("CodeQL analysis completed successfully")

        sarif_path = repo_path / "codeql-agent-results" / "issues.sarif"
        if not sarif_path.exists():
            raise RuntimeError(f"SARIF results file not found at {sarif_path}")

        return sarif_path

    except subprocess.CalledProcessError as e:
        logger.error(f"Docker command failed: {e.stderr}")
        raise RuntimeError(f"CodeQL analysis failed: {e.stderr}")
    except Exception as e:
        logger.error(f"Unexpected error during CodeQL analysis: {e}")
        raise RuntimeError(f"CodeQL analysis failed: {str(e)}")


def _parse_kv_message(text: str) -> dict[str, str]:
    """Parse KV-encoded message text into a dict."""
    result: dict[str, str] = {}
    if not text:
        return result
    for chunk in text.split("|"):
        if not chunk:
            continue
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        if not key:
            continue
        result[key] = value
    return result


def _parse_sarif_for_rule(sarif_path: Path, rule_id: str) -> list[dict[str, str]]:
    """Parse SARIF results and return KV-parsed messages for a rule."""
    logger.info(f"Parsing SARIF results from {sarif_path}")

    with open(sarif_path) as f:
        sarif_data = json.load(f)

    results: list[dict[str, str]] = []
    for run in sarif_data.get("runs", []):
        for result in run.get("results", []):
            if result.get("ruleId", "") != rule_id:
                continue
            message_text = result.get("message", {}).get("text", "")
            parsed = _parse_kv_message(message_text)
            if parsed:
                results.append(parsed)
    return results


def _cleanup_analysis_files(repo_path: Path) -> None:
    """Remove temporary CodeQL analysis files and directories.

    Args:
        repo_path: Path to the repository where analysis files were created
    """
    logger.info("Cleaning up CodeQL analysis files...")

    queries_dir = repo_path / "codeql-queries"
    if queries_dir.exists():
        try:
            shutil.rmtree(queries_dir)
            logger.info(f"Removed {queries_dir}")
        except Exception as e:
            logger.warning(f"Failed to remove {queries_dir}: {e}")

    results_dir = repo_path / "codeql-agent-results"
    if results_dir.exists():
        try:
            shutil.rmtree(results_dir)
            logger.info(f"Removed {results_dir}")
        except Exception as e:
            logger.warning(f"Failed to remove {results_dir}: {e}")


def _run_query_tool(repo_path: str, query_text: str, rule_id: str) -> str:
    logger.info(f"Starting TeaStore CodeQL analysis for: {repo_path}")
    repo_path_obj = Path(repo_path).resolve()

    # Validate repository path
    if not repo_path_obj.exists():
        error_msg = f"Repository path does not exist: {repo_path}"
        logger.error(error_msg)
        return json.dumps(
            {"success": False, "error": error_msg, "endpoints": [], "microservices": []},
            indent=2,
        )

    try:
        queries_dir = repo_path_obj / "codeql-queries"
        _create_query_files(queries_dir, query_text, rule_id)

        sarif_path = _run_codeql_analysis(repo_path_obj)
        results = _parse_sarif_for_rule(sarif_path, rule_id)

        # Step 5: Clean up temporary files
        _cleanup_analysis_files(repo_path_obj)

        logger.info("TeaStore CodeQL analysis completed successfully")
        return json.dumps(
            {
                "success": True,
                "rule_id": rule_id,
                "results": results,
                "total_findings": len(results),
            },
            indent=2,
        )
    except Exception as e:
        error_msg = f"CodeQL analysis failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps(
            {
                "success": False,
                "rule_id": rule_id,
                "results": [],
                "total_findings": 0,
                "error": error_msg,
            },
            indent=2,
        )
    finally:
        try:
            _cleanup_analysis_files(repo_path_obj)
        except Exception as cleanup_error:
            logger.warning(f"Cleanup failed after error: {cleanup_error}")


# ============================================================================
# CODEQL ANALYSIS TOOLS
# ============================================================================


@tool
def teastore_find_microservices(repo_path: str) -> str:
    """Find TeaStore microservices for the environment summary.

    Returns JSON:
    {
      "success": bool,
      "rule_id": "teastore/find-microservices",
      "results": [ {kv pairs...}, ... ],
      "total_findings": int,
      "error": optional str
    }
    """
    return _run_query_tool(repo_path, FIND_MICROSERVICES_QUERY, "teastore/find-microservices")


@tool
def teastore_find_endpoints(repo_path: str) -> str:
    """Find TeaStore endpoints for the environment summary.

    Returns JSON:
    {
      "success": bool,
      "rule_id": "teastore/find-endpoints",
      "results": [ {kv pairs...}, ... ],
      "total_findings": int,
      "error": optional str
    }
    """
    return _run_query_tool(repo_path, FIND_ENDPOINTS_QUERY, "teastore/find-endpoints")


@tool
def teastore_component_inventory(repo_path: str) -> str:
    """Component Summary Agent tool: component inventory.

    Returns JSON:
    {
      "success": bool,
      "rule_id": "teastore/component-inventory",
      "results": [ {kv pairs...}, ... ],
      "total_findings": int,
      "error": optional str
    }
    """
    return _run_query_tool(repo_path, COMPONENT_INVENTORY_QUERY, "teastore/component-inventory")


@tool
def teastore_hierarchical_composition(repo_path: str) -> str:
    """Component Summary Agent tool: hierarchical composition.

    Returns JSON:
    {
      "success": bool,
      "rule_id": "teastore/hierarchical-composition",
      "results": [ {kv pairs...}, ... ],
      "total_findings": int,
      "error": optional str
    }
    """
    return _run_query_tool(repo_path, HIERARCHICAL_COMPOSITION_QUERY, "teastore/hierarchical-composition")


@tool
def teastore_exported_http_endpoints(repo_path: str) -> str:
    """Component Summary Agent tool: exported HTTP endpoints.

    Returns JSON:
    {
      "success": bool,
      "rule_id": "teastore/exported-http-endpoints",
      "results": [ {kv pairs...}, ... ],
      "total_findings": int,
      "error": optional str
    }
    """
    return _run_query_tool(repo_path, EXPORTED_HTTP_ENDPOINTS_QUERY, "teastore/exported-http-endpoints")


@tool
def teastore_exported_public_api(repo_path: str) -> str:
    """Component Summary Agent tool: exported public API surface.

    Returns JSON:
    {
      "success": bool,
      "rule_id": "teastore/exported-public-api",
      "results": [ {kv pairs...}, ... ],
      "total_findings": int,
      "error": optional str
    }
    """
    return _run_query_tool(repo_path, EXPORTED_PUBLIC_API_QUERY, "teastore/exported-public-api")


@tool
def teastore_deps_call_based(repo_path: str) -> str:
    """Component Summary Agent tool: call-based dependencies.

    Returns JSON:
    {
      "success": bool,
      "rule_id": "teastore/deps-call-based",
      "results": [ {kv pairs...}, ... ],
      "total_findings": int,
      "error": optional str
    }
    """
    return _run_query_tool(repo_path, DEPS_CALL_BASED_QUERY, "teastore/deps-call-based")


@tool
def teastore_deps_type_based(repo_path: str) -> str:
    """Component Summary Agent tool: type-based dependencies.

    Returns JSON:
    {
      "success": bool,
      "rule_id": "teastore/deps-type-based",
      "results": [ {kv pairs...}, ... ],
      "total_findings": int,
      "error": optional str
    }
    """
    return _run_query_tool(repo_path, DEPS_TYPE_BASED_QUERY, "teastore/deps-type-based")


@tool
def teastore_deps_resource_based(repo_path: str) -> str:
    """Component Summary Agent tool: resource-based dependencies.

    Returns JSON:
    {
      "success": bool,
      "rule_id": "teastore/deps-resource-based",
      "results": [ {kv pairs...}, ... ],
      "total_findings": int,
      "error": optional str
    }
    """
    return _run_query_tool(repo_path, DEPS_RESOURCE_BASED_QUERY, "teastore/deps-resource-based")


@tool
def teastore_rooted_call_graph_depth5(repo_path: str) -> str:
    """Behavior Summary Agent tool: rooted call graph depth 5.

    Returns JSON:
    {
      "success": bool,
      "rule_id": "teastore/rooted-call-graph-depth5",
      "results": [ {kv pairs...}, ... ],
      "total_findings": int,
      "error": optional str
    }
    """
    return _run_query_tool(repo_path, ROOTED_CALL_GRAPH_DEPTH5_QUERY, "teastore/rooted-call-graph-depth5")


@tool
def teastore_control_flow_structure(repo_path: str) -> str:
    """Behavior Summary Agent tool: control flow structure.

    Returns JSON:
    {
      "success": bool,
      "rule_id": "teastore/control-flow-structure",
      "results": [ {kv pairs...}, ... ],
      "total_findings": int,
      "error": optional str
    }
    """
    return _run_query_tool(repo_path, CONTROL_FLOW_STRUCTURE_QUERY, "teastore/control-flow-structure")


@tool
def teastore_interaction_sites(repo_path: str) -> str:
    """Behavior Summary Agent tool: interaction sites.

    Returns JSON:
    {
      "success": bool,
      "rule_id": "teastore/interaction-sites",
      "results": [ {kv pairs...}, ... ],
      "total_findings": int,
      "error": optional str
    }
    """
    return _run_query_tool(repo_path, INTERACTION_SITES_QUERY, "teastore/interaction-sites")


@tool
def teastore_synchronization_constructs(repo_path: str) -> str:
    """Behavior Summary Agent tool: synchronization constructs.

    Returns JSON:
    {
      "success": bool,
      "rule_id": "teastore/synchronization-constructs",
      "results": [ {kv pairs...}, ... ],
      "total_findings": int,
      "error": optional str
    }
    """
    return _run_query_tool(repo_path, SYNCHRONIZATION_CONSTRUCTS_QUERY, "teastore/synchronization-constructs")
