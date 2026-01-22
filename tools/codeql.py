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
# CODEQL QUERY FILE TEMPLATES (OPTIMIZED)
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
select c, "kind=microservice|service=" + serviceName + "|component_fqn=" + c.getQualifiedName()
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
select c, "kind=endpoint|service=" + serviceName + "|endpoint_fqn=" + c.getQualifiedName()
"""

COMPONENT_INVENTORY_QUERY = """/**
 * @name TeaStore Component Inventory (Filtered)
 * @description Lists only significant packages, endpoint classes, and service classes
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

predicate isSignificantClass(Class c) {
  c.getName().matches("%Servlet") or
  c.getName().matches("%Endpoint") or
  c.getName().matches("%Rest") or
  c.getName().matches("%Service") or
  c.getName().matches("%Controller") or
  c.getName().matches("%Application") or
  c.getName().matches("%Registry") or
  c.getName().matches("%Repository") or
  c.getName().matches("%Manager") or
  c.getName().matches("%Handler") or
  c.getName().matches("%Dao") or
  c.getName().matches("%Entity")
}

from Element e, string kind, string fqn, string serviceName, string message
where
  // Only top-level service packages (not every subpackage)
  (
    exists(Package p |
      e = p and
      serviceName = getMicroserviceFromPackage(p) and
      // Only capture direct service packages, not nested ones
      p.getName().regexpMatch("tools\\\\.descartes\\\\.teastore\\\\.[^.]+") and
      kind = "package" and
      fqn = p.getName() and
      message = "kind=component|component_type=package|service=" + serviceName + "|fqn=" + fqn
    )
  )
  or
  // Only significant classes (endpoints, services, etc.)
  (
    exists(Class c |
      e = c and
      c.fromSource() and
      isSignificantClass(c) and
      serviceName = getMicroserviceFromPackage(c.getPackage()) and
      kind = "class" and
      fqn = c.getQualifiedName() and
      message = "kind=component|component_type=class|service=" + serviceName + "|fqn=" + fqn
    )
  )
select e, message
"""

HIERARCHICAL_COMPOSITION_QUERY = """/**
 * @name TeaStore Hierarchical Composition (Service Level)
 * @description Captures service-to-package and package-to-class relationships only
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

predicate isSignificantClass(Class c) {
  c.getName().matches("%Servlet") or
  c.getName().matches("%Endpoint") or
  c.getName().matches("%Rest") or
  c.getName().matches("%Service") or
  c.getName().matches("%Controller") or
  c.getName().matches("%Repository") or
  c.getName().matches("%Manager") or
  c.getName().matches("%Handler") or
  c.getName().matches("%Dao") or
  c.getName().matches("%Entity")
}

from Element child, string serviceName, string parentFqn, string childFqn, string relType
where
  // Package contains significant classes only
  (
    exists(Package p, Class c |
      c.getPackage() = p and
      serviceName = getMicroserviceFromPackage(p) and
      isSignificantClass(c) and
      c.fromSource() and
      child = c and
      parentFqn = p.getName() and
      childFqn = c.getQualifiedName() and
      relType = "package_to_class"
    )
  )
  or
  // Class inheritance (only for significant classes)
  (
    exists(Class sub, Class sup |
      sub.fromSource() and
      isSignificantClass(sub) and
      sup = sub.getASupertype() and
      sup instanceof Class and
      serviceName = getMicroserviceFromPackage(sub.getPackage()) and
      child = sub and
      parentFqn = sup.getQualifiedName() and
      childFqn = sub.getQualifiedName() and
      relType = "inheritance"
    )
  )
select child, "kind=hierarchical_composition|service=" + serviceName +
  "|relation=" + relType +
  "|parent=" + parentFqn +
  "|child=" + childFqn
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
   c.getPackage().getName().matches("%.rest") or
   c.getName().matches("%Servlet") or
   c.getName().matches("%Controller")) and
  c.fromSource()
select c, "kind=exported_http_endpoint|service=" + serviceName + "|endpoint_fqn=" + c.getQualifiedName()
"""

EXPORTED_PUBLIC_API_QUERY = """/**
 * @name TeaStore Exported Public API (Entry Points Only)
 * @description Captures only public entry point methods (endpoints, services)
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

predicate isEntryPointClass(Class c) {
  c.getName().matches("%Servlet") or
  c.getName().matches("%Endpoint") or
  c.getName().matches("%Rest") or
  c.getName().matches("%Controller") or
  c.getName().matches("%Service") or
  c.getPackage().getName().matches("%.rest") or
  c.getPackage().getName().matches("%.servlet")
}

from Method m, string serviceName
where
  m.isPublic() and
  isEntryPointClass(m.getDeclaringType()) and
  serviceName = getMicroserviceFromPackage(m.getDeclaringType().getPackage()) and
  m.fromSource()
select m, "kind=exported_public_api|service=" + serviceName +
  "|class=" + m.getDeclaringType().getQualifiedName() +
  "|method=" + m.getName() +
  "|signature=" + m.getStringSignature()
"""

DEPS_CALL_BASED_QUERY = """/**
 * @name TeaStore Call-Based Dependencies (Aggregated)
 * @description Captures class-to-class dependencies via method calls
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/deps-call-based
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\\\.descartes\\\\.teastore\\\\.([^.]+).*", 1)
  )
}

from Class fromClass, Class toClass, string fromService, string toService
where
  exists(MethodCall call |
    call.getEnclosingCallable().getDeclaringType() = fromClass and
    call.getMethod().getDeclaringType() = toClass and
    fromClass.fromSource() and
    fromService = getMicroserviceFromPackage(fromClass.getPackage()) and
    toService = getMicroserviceFromPackage(toClass.getPackage()) and
    fromClass != toClass  // Exclude self-calls
  )
select fromClass, "kind=call_dependency|from_service=" + fromService +
  "|from_class=" + fromClass.getQualifiedName() +
  "|to_service=" + toService +
  "|to_class=" + toClass.getQualifiedName()
"""

DEPS_RESOURCE_BASED_QUERY = """/**
 * @name TeaStore Resource-Based Dependencies
 * @description Captures resource references (URLs, file paths)
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/deps-resource-based
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\\\.descartes\\\\.teastore\\\\.([^.]+).*", 1)
  )
}

from StringLiteral s, Class c, string serviceName
where
  (s.getValue().matches("%http%") or s.getValue().matches("%/api/%")) and
  c = s.getEnclosingCallable().getDeclaringType() and
  c.fromSource() and
  serviceName = getMicroserviceFromPackage(c.getPackage())
select s, "kind=deps_resource_based|service=" + serviceName +
  "|class=" + c.getQualifiedName() +
  "|value=" + s.getValue()
"""

ROOTED_CALL_GRAPH_DEPTH5_QUERY = """/**
 * @name TeaStore Rooted Call Graph (Class Level)
 * @description Captures interprocedural call graph edges at class level within TeaStore packages
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/rooted-call-graph-depth5
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\\\.descartes\\\\.teastore\\\\.([^.]+).*", 1)
  )
}

from Class callerClass, Class calleeClass, string fromService, string toService
where
  exists(MethodCall call |
    call.getEnclosingCallable().getDeclaringType() = callerClass and
    call.getMethod().getDeclaringType() = calleeClass and
    callerClass.getPackage().getName().matches("tools.descartes.teastore.%") and
    calleeClass.getPackage().getName().matches("tools.descartes.teastore.%") and
    fromService = getMicroserviceFromPackage(callerClass.getPackage()) and
    toService = getMicroserviceFromPackage(calleeClass.getPackage()) and
    callerClass != calleeClass
  )
select callerClass, "kind=call_graph_edge|from_service=" + fromService +
  "|caller=" + callerClass.getQualifiedName() +
  "|to_service=" + toService +
  "|callee=" + calleeClass.getQualifiedName()
"""

CONTROL_FLOW_STRUCTURE_QUERY = """/**
 * @name TeaStore Control Flow Structure (Aggregated)
 * @description Captures control-flow statement counts per class
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/control-flow-structure
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\\\.descartes\\\\.teastore\\\\.([^.]+).*", 1)
  )
}

predicate isSignificantClass(Class c) {
  c.getName().matches("%Servlet") or
  c.getName().matches("%Endpoint") or
  c.getName().matches("%Rest") or
  c.getName().matches("%Service") or
  c.getName().matches("%Controller") or
  c.getName().matches("%Repository") or
  c.getName().matches("%Manager") or
  c.getName().matches("%Handler")
}

from Class c, string serviceName, int ifCount, int forCount, int whileCount, int switchCount
where
  c.fromSource() and
  isSignificantClass(c) and
  serviceName = getMicroserviceFromPackage(c.getPackage()) and
  ifCount = count(IfStmt s | s.getEnclosingCallable().getDeclaringType() = c) and
  forCount = count(ForStmt s | s.getEnclosingCallable().getDeclaringType() = c) and
  whileCount = count(WhileStmt s | s.getEnclosingCallable().getDeclaringType() = c) and
  switchCount = count(SwitchStmt s | s.getEnclosingCallable().getDeclaringType() = c) and
  (ifCount > 0 or forCount > 0 or whileCount > 0 or switchCount > 0)
select c, "kind=control_flow_structure|service=" + serviceName +
  "|class=" + c.getQualifiedName() +
  "|if_count=" + ifCount +
  "|for_count=" + forCount +
  "|while_count=" + whileCount +
  "|switch_count=" + switchCount
"""

INTERACTION_SITES_QUERY = """/**
 * @name TeaStore Interaction Sites (Aggregated)
 * @description Captures external calls and database access sites aggregated by class
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/interaction-sites
 */

import java

string getMicroserviceFromPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    pkgName.matches("tools.descartes.teastore.%") and
    result = pkgName.regexpCapture("tools\\\\.descartes\\\\.teastore\\\\.([^.]+).*", 1)
  )
}

predicate isDbPackage(Package p) {
  exists(string pkgName |
    pkgName = p.getName() and
    (
      pkgName.matches("java.sql%") or
      pkgName.matches("javax.sql%") or
      pkgName.matches("javax.persistence%") or
      pkgName.matches("org.hibernate%") or
      pkgName.matches("org.springframework.jdbc%") or
      pkgName.matches("org.springframework.data%")
    )
  )
}

from Class c, string serviceName, string targetPackage, string interactionType
where
  c.fromSource() and
  serviceName = getMicroserviceFromPackage(c.getPackage()) and
  exists(MethodCall call, Package targetPkg |
    call.getEnclosingCallable().getDeclaringType() = c and
    targetPkg = call.getMethod().getDeclaringType().getPackage() and
    targetPackage = targetPkg.getName() and
    not targetPackage.matches("tools.descartes.teastore.%") and
    (
      (isDbPackage(targetPkg) and interactionType = "db_access") or
      (not isDbPackage(targetPkg) and interactionType = "external_call")
    )
  )
select c, "kind=interaction_site|service=" + serviceName +
  "|class=" + c.getQualifiedName() +
  "|type=" + interactionType +
  "|target_package=" + targetPackage
"""

SYNCHRONIZATION_CONSTRUCTS_QUERY = """/**
 * @name TeaStore Synchronization Constructs
 * @description Captures synchronized blocks and methods
 * @kind problem
 * @problem.severity recommendation
 * @id teastore/synchronization-constructs
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
  m.isSynchronized() and
  m.fromSource() and
  serviceName = getMicroserviceFromPackage(m.getDeclaringType().getPackage())
select m, "kind=synchronization_construct|service=" + serviceName +
  "|type=method|class=" + m.getDeclaringType().getQualifiedName() +
  "|method=" + m.getName()
"""

QLPACK_YML = """name: teastore/microservice-analysis
version: 0.0.1
libraryPathDependencies:
  - codeql/java-all
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _create_query_files_multi(
    queries_dir: Path, queries: dict[str, str], rule_ids: list[str], tool_name: str
) -> None:
    """Write multiple CodeQL query files to the specified directory.

    Args:
        queries_dir: Directory where query files should be written
        queries: Dict mapping query filenames to query text
        rule_ids: List of rule IDs to include in the suite
        tool_name: Tool name for unique directory naming
    """
    queries_dir.mkdir(parents=True, exist_ok=True)

    # Write all query files
    for filename, query_text in queries.items():
        (queries_dir / filename).write_text(query_text)

    # Create suite that includes all queries
    suite_rules = "\n      - ".join(rule_ids)
    suite_text = f"""- description: TeaStore Multi-Query Analysis
- queries: .
- include:
    id:
      - {suite_rules}
"""

    (queries_dir / "teastore-analysis.qls").write_text(suite_text)
    (queries_dir / "qlpack.yml").write_text(QLPACK_YML)

    logger.info(f"Created {len(queries)} CodeQL query files in {queries_dir} for {tool_name}")


def _run_codeql_analysis(repo_path: Path, tool_name: str, queries_dir_name: str) -> Path:
    """Run CodeQL analysis using Docker container.

    Args:
        repo_path: Path to the TeaStore repository
        tool_name: Tool name for unique container naming
        queries_dir_name: Name of the queries directory

    Returns:
        Path to the SARIF results file

    Raises:
        RuntimeError: If Docker command fails
    """
    logger.info(f"Running CodeQL analysis via Docker for {tool_name}...")

    # Use unique container name based on tool
    container_name = f"codeql-{tool_name.replace('_', '-')}"

    # Use tool-specific results directory
    results_dir_name = f"codeql-agent-results-{tool_name}"

    # Docker command from run-analysis.sh
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "-v",
        f"{repo_path}:/opt/src",
        "-v",
        f"{repo_path}/{results_dir_name}:/opt/results",
        "-e",
        "LANGUAGE=java",
        "-e",
        "COMMAND=mvn clean compile -DskipTests -Dmaven.repo.local=/opt/src/build-local",
        "-e",
        f"QS=/opt/src/{queries_dir_name}/teastore-analysis.qls",
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

        logger.info(f"CodeQL analysis completed successfully for {tool_name}")

        sarif_path = repo_path / results_dir_name / "issues.sarif"
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


def _parse_sarif_multi(sarif_path: Path, rule_ids: list[str]) -> dict[str, list[dict[str, str]]]:
    """Parse SARIF results for multiple rules and return grouped by rule ID with deduplication.

    OPTIMIZATION: Deduplicates results to reduce output size while preserving all unique
    architectural information.
    """
    logger.info(f"Parsing SARIF results from {sarif_path} for {len(rule_ids)} rules")

    with open(sarif_path) as f:
        sarif_data = json.load(f)

    # Initialize results dict for all rule IDs
    results_by_rule: dict[str, list[dict[str, str]]] = {rule_id: [] for rule_id in rule_ids}

    # Track seen items to deduplicate (exclude file/line metadata for dedup key)
    seen_by_rule: dict[str, set[str]] = {rule_id: set() for rule_id in rule_ids}

    for run in sarif_data.get("runs", []):
        for result in run.get("results", []):
            rule_id = result.get("ruleId", "")
            if rule_id not in rule_ids:
                continue
            message_text = result.get("message", {}).get("text", "")
            parsed = _parse_kv_message(message_text)
            if parsed:
                # Create dedup key (exclude file/line info if present)
                dedup_key = "|".join(f"{k}={v}" for k, v in sorted(parsed.items())
                                    if k not in ['file', 'start_line', 'end_line'])

                if dedup_key not in seen_by_rule[rule_id]:
                    seen_by_rule[rule_id].add(dedup_key)
                    results_by_rule[rule_id].append(parsed)

    # Log deduplication stats
    total_unique = sum(len(results) for results in results_by_rule.values())
    logger.info(f"Parsed {total_unique} unique results after deduplication")

    return results_by_rule


def _cleanup_analysis_files(repo_path: Path, queries_dir_name: str, tool_name: str) -> None:
    """Remove temporary CodeQL analysis files and directories.

    Args:
        repo_path: Path to the repository where analysis files were created
        queries_dir_name: Name of the queries directory to remove
        tool_name: Tool name for unique results directory naming
    """
    logger.info(f"Cleaning up CodeQL analysis files for {tool_name}...")

    queries_dir = repo_path / queries_dir_name
    if queries_dir.exists():
        try:
            shutil.rmtree(queries_dir)
            logger.info(f"Removed {queries_dir}")
        except Exception as e:
            logger.warning(f"Failed to remove {queries_dir}: {e}")

    results_dir_name = f"codeql-agent-results-{tool_name}"
    results_dir = repo_path / results_dir_name
    if results_dir.exists():
        try:
            shutil.rmtree(results_dir)
            logger.info(f"Removed {results_dir}")
        except Exception as e:
            logger.warning(f"Failed to remove {results_dir}: {e}")


def _run_multi_query_tool(
    repo_path: str, queries: dict[str, str], rule_ids: list[str], tool_name: str
) -> str:
    """Run multiple CodeQL queries and return combined results."""
    logger.info(f"Starting TeaStore CodeQL multi-query analysis with {tool_name} for: {repo_path}")
    repo_path_obj = Path(repo_path).resolve()

    # Create unique directory names based on tool
    queries_dir_name = f"codeql-queries-{tool_name}"

    # Validate repository path
    if not repo_path_obj.exists():
        error_msg = f"Repository path does not exist: {repo_path}"
        logger.error(error_msg)
        return json.dumps(
            {"success": False, "error": error_msg, "results": {}},
            indent=2,
        )

    try:
        queries_dir = repo_path_obj / queries_dir_name
        _create_query_files_multi(queries_dir, queries, rule_ids, tool_name)

        sarif_path = _run_codeql_analysis(repo_path_obj, tool_name, queries_dir_name)
        results_by_rule = _parse_sarif_multi(sarif_path, rule_ids)

        # Clean up temporary files
        _cleanup_analysis_files(repo_path_obj, queries_dir_name, tool_name)

        # Calculate total findings
        total_findings = sum(len(results) for results in results_by_rule.values())

        logger.info(f"TeaStore CodeQL analysis completed successfully for {tool_name}")
        logger.info(f"Total unique findings: {total_findings}")

        return json.dumps(
            {
                "success": True,
                "results": results_by_rule,
                "total_findings": total_findings,
            },
            indent=2,
        )
    except Exception as e:
        error_msg = f"CodeQL analysis failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps(
            {
                "success": False,
                "results": {},
                "total_findings": 0,
                "error": error_msg,
            },
            indent=2,
        )
    finally:
        try:
            _cleanup_analysis_files(repo_path_obj, queries_dir_name, tool_name)
        except Exception as cleanup_error:
            logger.warning(f"Cleanup failed after error: {cleanup_error}")


# ============================================================================
# CODEQL COMBINED ANALYSIS TOOLS (OPTIMIZED)
# ============================================================================


@tool
def teastore_component_analysis(repo_path: str) -> str:
    """Comprehensive component analysis for TeaStore architecture (OPTIMIZED).

    Runs all component-related CodeQL queries in a single analysis pass:
    - Microservice identification (package structure analysis)
    - Endpoint discovery (servlets, REST endpoints, controllers)
    - Component inventory (FILTERED: only significant classes, no methods)
    - Hierarchical composition (FILTERED: only significant relationships)
    - Exported HTTP endpoints (public API surface)
    - Exported public API (FILTERED: only entry point methods)
    - Call-based dependencies (AGGREGATED: class-level instead of method-level)
    - Resource-based dependencies (URLs, file paths with context)

    This tool is optimized for ComponentSummarizerAgent to gather complete structural information
    about the TeaStore microservices architecture in a single Docker run.

    Returns JSON:
    {
      "success": bool,
      "results": {
        "teastore/find-microservices-simple": [{kv pairs...}, ...],
        "teastore/find-all-endpoints": [{kv pairs...}, ...],
        "teastore/component-inventory": [{kv pairs...}, ...],
        "teastore/hierarchical-composition": [{kv pairs...}, ...],
        "teastore/exported-http-endpoints": [{kv pairs...}, ...],
        "teastore/exported-public-api": [{kv pairs...}, ...],
        "teastore/deps-call-based": [{kv pairs...}, ...],
        "teastore/deps-resource-based": [{kv pairs...}, ...]
      },
      "total_findings": int,
      "error": optional str
    }
    """
    queries = {
        "find-microservices.ql": FIND_MICROSERVICES_QUERY,
        "find-endpoints.ql": FIND_ENDPOINTS_QUERY,
        "component-inventory.ql": COMPONENT_INVENTORY_QUERY,
        "hierarchical-composition.ql": HIERARCHICAL_COMPOSITION_QUERY,
        "exported-http-endpoints.ql": EXPORTED_HTTP_ENDPOINTS_QUERY,
        "exported-public-api.ql": EXPORTED_PUBLIC_API_QUERY,
        "deps-call-based.ql": DEPS_CALL_BASED_QUERY,
        "deps-resource-based.ql": DEPS_RESOURCE_BASED_QUERY,
    }

    rule_ids = [
        "teastore/find-microservices-simple",
        "teastore/find-all-endpoints",
        "teastore/component-inventory",
        "teastore/hierarchical-composition",
        "teastore/exported-http-endpoints",
        "teastore/exported-public-api",
        "teastore/deps-call-based",
        "teastore/deps-resource-based",
    ]

    return _run_multi_query_tool(repo_path, queries, rule_ids, "component_analysis")


@tool
def teastore_behavior_analysis(repo_path: str) -> str:
    """Comprehensive behavior analysis for TeaStore execution patterns (OPTIMIZED).

    Runs all behavior-related CodeQL queries in a single analysis pass:
    - Rooted call graph (AGGREGATED: class-level interprocedural calls)
    - Control flow structure (AGGREGATED: statement counts per class)
    - Interaction sites (AGGREGATED: external calls and database access by class)
    - Synchronization constructs (thread-safety mechanisms)

    This tool is optimized for BehaviorSummarizerAgent to gather complete runtime behavior
    information about the TeaStore microservices in a single Docker run.

    Returns JSON:
    {
      "success": bool,
      "results": {
        "teastore/rooted-call-graph-depth5": [{kv pairs...}, ...],
        "teastore/control-flow-structure": [{kv pairs...}, ...],
        "teastore/interaction-sites": [{kv pairs...}, ...],
        "teastore/synchronization-constructs": [{kv pairs...}, ...]
      },
      "total_findings": int,
      "error": optional str
    }
    """
    queries = {
        "rooted-call-graph-depth5.ql": ROOTED_CALL_GRAPH_DEPTH5_QUERY,
        "control-flow-structure.ql": CONTROL_FLOW_STRUCTURE_QUERY,
        "interaction-sites.ql": INTERACTION_SITES_QUERY,
        "synchronization-constructs.ql": SYNCHRONIZATION_CONSTRUCTS_QUERY,
    }

    rule_ids = [
        "teastore/rooted-call-graph-depth5",
        "teastore/control-flow-structure",
        "teastore/interaction-sites",
        "teastore/synchronization-constructs",
    ]

    return _run_multi_query_tool(repo_path, queries, rule_ids, "behavior_analysis")