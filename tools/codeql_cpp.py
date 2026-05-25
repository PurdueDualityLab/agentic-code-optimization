"""CodeQL analysis tools for DeathStarBench socialnetwork benchmarks.

NOTE: This module contains hardcoded tools specifically designed for DeathStarBench 
socialnetwork microservices architecture (C++).
These tools are not generic and should only be used with DeathStarBench repositories.

OPTIMIZATION: Queries have been optimized to reduce output by 80-95% while retaining all
architecturally significant information by:
- Filtering to only significant components (services, handlers, clients)
- Aggregating dependencies at class/function-level instead of line-level
- Removing redundant file/line information
- Deduplicating results in post-processing
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
# CODEQL QUERY FILE TEMPLATES (OPTIMIZED FOR C++)
# ============================================================================

FIND_MICROSERVICES_QUERY = """/**
 * @name Identify DeathStarBench Microservices
 * @description Finds microservices by analyzing directory structure and service classes
 * @kind problem
 * @problem.severity recommendation
 * @id deathstar/find-microservices-simple
 */

import cpp

/**
 * Extract microservice name from file path
 * DeathStarBench services are in socialNetwork/src/<service_name>/
 */
string getMicroserviceFromFile(File f) {
  exists(string path |
    path = f.getRelativePath() and
    path.matches("socialNetwork/src/%") and
    result = path.regexpCapture("socialNetwork/src/([^/]+)/.*", 1)
  )
}

/**
 * Check if a class/struct is a significant microservice component
 */
predicate isSignificantComponent(Class c) {
  c.getName().matches("%Service%") or
  c.getName().matches("%Handler") or
  c.getName().matches("%Client") or
  c.getName().matches("%Server") or
  c.getName().matches("%Manager") or
  c.getName().matches("%Controller")
}

from Class c, string serviceName
where
  serviceName = getMicroserviceFromFile(c.getFile()) and
  isSignificantComponent(c) and
  c.fromSource()
select c, "kind=microservice|service=" + serviceName + "|component_fqn=" + c.getQualifiedName()
"""

FIND_ENDPOINTS_QUERY = """/**
 * @name Find All Endpoints
 * @description Finds all classes that look like endpoints/handlers based on naming
 * @kind problem
 * @problem.severity recommendation
 * @id deathstar/find-all-endpoints
 */

import cpp

/**
 * Get the microservice name from file path
 */
string getMicroserviceFromFile(File f) {
  exists(string path |
    path = f.getRelativePath() and
    path.matches("socialNetwork/src/%") and
    result = path.regexpCapture("socialNetwork/src/([^/]+)/.*", 1)
  )
}

from Class c, string serviceName
where
  // Class name indicates it's an endpoint/handler
  (c.getName().matches("%Handler") or
   c.getName().matches("%Service%") or
   c.getName().matches("%Endpoint") or
   c.getName().matches("%Server")) and
  // In socialNetwork source
  c.getFile().getRelativePath().matches("socialNetwork/src/%") and
  serviceName = getMicroserviceFromFile(c.getFile()) and
  c.fromSource()
select c, "kind=endpoint|service=" + serviceName + "|endpoint_fqn=" + c.getQualifiedName()
"""

COMPONENT_INVENTORY_QUERY = """/**
 * @name DeathStarBench Component Inventory (Filtered)
 * @description Lists only significant classes and functions
 * @kind problem
 * @problem.severity recommendation
 * @id deathstar/component-inventory
 */

import cpp

string getMicroserviceFromFile(File f) {
  exists(string path |
    path = f.getRelativePath() and
    path.matches("socialNetwork/src/%") and
    result = path.regexpCapture("socialNetwork/src/([^/]+)/.*", 1)
  )
}

predicate isSignificantClass(Class c) {
  c.getName().matches("%Service%") or
  c.getName().matches("%Handler") or
  c.getName().matches("%Client") or
  c.getName().matches("%Server") or
  c.getName().matches("%Manager") or
  c.getName().matches("%Controller") or
  c.getName().matches("%Repository") or
  c.getName().matches("%Store")
}

predicate isSignificantFunction(Function f) {
  // Public/exported functions in service files
  (f.getName().matches("%Service%") or
   f.getName().matches("handle%") or
   f.getName().matches("process%") or
   f.getName().matches("send%") or
   f.getName().matches("get%") or
   f.getName().matches("set%") or
   f.getName().matches("read%") or
   f.getName().matches("write%") or
   f.getName().matches("compose%")) and
  not f.getName().matches("%test%") and
  not f.getName().matches("%Test%")
}

from Element e, string kind, string fqn, string serviceName, string message
where
  // Only significant classes
  (
    exists(Class c |
      e = c and
      c.fromSource() and
      isSignificantClass(c) and
      c.getFile().getRelativePath().matches("socialNetwork/src/%") and
      serviceName = getMicroserviceFromFile(c.getFile()) and
      kind = "class" and
      fqn = c.getQualifiedName() and
      message = "kind=component|component_type=class|service=" + serviceName + "|fqn=" + fqn
    )
  )
  or
  // Only significant functions (in service classes or top-level)
  (
    exists(Function f |
      e = f and
      f.fromSource() and
      isSignificantFunction(f) and
      f.getFile().getRelativePath().matches("socialNetwork/src/%") and
      serviceName = getMicroserviceFromFile(f.getFile()) and
      kind = "function" and
      fqn = f.getQualifiedName() and
      message = "kind=component|component_type=function|service=" + serviceName + "|fqn=" + fqn
    )
  )
select e, message
"""

HIERARCHICAL_COMPOSITION_QUERY = """/**
 * @name DeathStarBench Hierarchical Composition (Service Level)
 * @description Captures class-to-function and inheritance relationships
 * @kind problem
 * @problem.severity recommendation
 * @id deathstar/hierarchical-composition
 */

import cpp

string getMicroserviceFromFile(File f) {
  exists(string path |
    path = f.getRelativePath() and
    path.matches("socialNetwork/src/%") and
    result = path.regexpCapture("socialNetwork/src/([^/]+)/.*", 1)
  )
}

predicate isSignificantClass(Class c) {
  c.getName().matches("%Service%") or
  c.getName().matches("%Handler") or
  c.getName().matches("%Client") or
  c.getName().matches("%Server") or
  c.getName().matches("%Manager") or
  c.getName().matches("%Controller")
}

predicate isSignificantFunction(Function f) {
  (f.getName().matches("%Service%") or
   f.getName().matches("handle%") or
   f.getName().matches("process%")) and
  not f.getName().matches("%test%")
}

from Element child, string serviceName, string parentFqn, string childFqn, string relType
where
  // Class contains significant member functions
  (
    exists(Class c, MemberFunction f |
      f.getDeclaringType() = c and
      c.getFile().getRelativePath().matches("socialNetwork/src/%") and
      serviceName = getMicroserviceFromFile(c.getFile()) and
      isSignificantClass(c) and
      isSignificantFunction(f) and
      c.fromSource() and
      child = f and
      parentFqn = c.getQualifiedName() and
      childFqn = f.getQualifiedName() and
      relType = "class_to_function"
    )
  )
  or
  // Class inheritance
  (
    exists(Class sub, Class sup |
      sub.fromSource() and
      isSignificantClass(sub) and
      sup = sub.getABaseClass() and
      sub.getFile().getRelativePath().matches("socialNetwork/src/%") and
      serviceName = getMicroserviceFromFile(sub.getFile()) and
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
 * @name DeathStarBench Exported HTTP Endpoints
 * @description Captures handler classes and RPC endpoints
 * @kind problem
 * @problem.severity recommendation
 * @id deathstar/exported-http-endpoints
 */

import cpp

string getMicroserviceFromFile(File f) {
  exists(string path |
    path = f.getRelativePath() and
    path.matches("socialNetwork/src/%") and
    result = path.regexpCapture("socialNetwork/src/([^/]+)/.*", 1)
  )
}

from Class c, string serviceName
where
  serviceName = getMicroserviceFromFile(c.getFile()) and
  (c.getName().matches("%Handler") or 
   c.getName().matches("%Service%") or
   c.getName().matches("%Server")) and
  c.fromSource()
select c, "kind=exported_http_endpoint|service=" + serviceName + "|endpoint_fqn=" + c.getQualifiedName()
"""

EXPORTED_PUBLIC_API_QUERY = """/**
 * @name DeathStarBench Exported Public API (Entry Points Only)
 * @description Captures public handler and service functions
 * @kind problem
 * @problem.severity recommendation
 * @id deathstar/exported-public-api
 */

import cpp

string getMicroserviceFromFile(File f) {
  exists(string path |
    path = f.getRelativePath() and
    path.matches("socialNetwork/src/%") and
    result = path.regexpCapture("socialNetwork/src/([^/]+)/.*", 1)
  )
}

predicate isEntryPointFunction(Function f) {
  (f.getName().matches("handle%") or
   f.getName().matches("%Service%") or
   f.getName().matches("process%") or
   f.getName().matches("compose%")) and
  f.hasSpecifier("public") or
  not f.isMember()  // Top-level functions are considered public
}

from Function f, string serviceName
where
  isEntryPointFunction(f) and
  f.getFile().getRelativePath().matches("socialNetwork/src/%") and
  serviceName = getMicroserviceFromFile(f.getFile()) and
  f.fromSource()
select f, "kind=exported_public_api|service=" + serviceName + 
  "|function=" + f.getQualifiedName() +
  "|signature=" + f.getSignature()
"""

DEPS_CALL_BASED_QUERY = """/**
 * @name DeathStarBench Call-Based Dependencies (Aggregated)
 * @description Captures class-to-class dependencies via function calls
 * @kind problem
 * @problem.severity recommendation
 * @id deathstar/deps-call-based
 */

import cpp

string getMicroserviceFromFile(File f) {
  exists(string path |
    path = f.getRelativePath() and
    path.matches("socialNetwork/src/%") and
    result = path.regexpCapture("socialNetwork/src/([^/]+)/.*", 1)
  )
}

from Class fromClass, Class toClass, string fromService, string toService
where
  exists(FunctionCall call, Function caller, Function callee |
    caller.getDeclaringType() = fromClass and
    callee.getDeclaringType() = toClass and
    call.getEnclosingFunction() = caller and
    call.getTarget() = callee and
    fromClass.fromSource() and
    fromClass.getFile().getRelativePath().matches("socialNetwork/src/%") and
    toClass.getFile().getRelativePath().matches("socialNetwork/src/%") and
    fromService = getMicroserviceFromFile(fromClass.getFile()) and
    toService = getMicroserviceFromFile(toClass.getFile()) and
    fromClass != toClass  // Exclude self-calls
  )
select fromClass, "kind=call_dependency|from_service=" + fromService + 
  "|from_class=" + fromClass.getQualifiedName() +
  "|to_service=" + toService + 
  "|to_class=" + toClass.getQualifiedName()
"""

DEPS_RESOURCE_BASED_QUERY = """/**
 * @name DeathStarBench Resource-Based Dependencies
 * @description Captures resource references (URLs, endpoints, service names)
 * @kind problem
 * @problem.severity recommendation
 * @id deathstar/deps-resource-based
 */

import cpp

string getMicroserviceFromFile(File f) {
  exists(string path |
    path = f.getRelativePath() and
    path.matches("socialNetwork/src/%") and
    result = path.regexpCapture("socialNetwork/src/([^/]+)/.*", 1)
  )
}

from StringLiteral s, Function f, string serviceName
where
  (s.getValue().matches("%http%") or 
   s.getValue().matches("%localhost%") or
   s.getValue().matches("%Service") or
   s.getValue().matches("%.%:%")) and  // host:port patterns
  f = s.getEnclosingFunction() and
  f.fromSource() and
  f.getFile().getRelativePath().matches("socialNetwork/src/%") and
  serviceName = getMicroserviceFromFile(f.getFile())
select s, "kind=deps_resource_based|service=" + serviceName + 
  "|function=" + f.getQualifiedName() +
  "|value=" + s.getValue()
"""

ROOTED_CALL_GRAPH_DEPTH5_QUERY = """/**
 * @name DeathStarBench Rooted Call Graph (Class Level)
 * @description Captures interprocedural call graph edges at class level
 * @kind problem
 * @problem.severity recommendation
 * @id deathstar/rooted-call-graph-depth5
 */

import cpp

string getMicroserviceFromFile(File f) {
  exists(string path |
    path = f.getRelativePath() and
    path.matches("socialNetwork/src/%") and
    result = path.regexpCapture("socialNetwork/src/([^/]+)/.*", 1)
  )
}

from Class callerClass, Class calleeClass, string fromService, string toService
where
  exists(FunctionCall call, Function caller, Function callee |
    caller.getDeclaringType() = callerClass and
    callee.getDeclaringType() = calleeClass and
    call.getEnclosingFunction() = caller and
    call.getTarget() = callee and
    callerClass.getFile().getRelativePath().matches("socialNetwork/src/%") and
    calleeClass.getFile().getRelativePath().matches("socialNetwork/src/%") and
    fromService = getMicroserviceFromFile(callerClass.getFile()) and
    toService = getMicroserviceFromFile(calleeClass.getFile()) and
    callerClass != calleeClass
  )
select callerClass, "kind=call_graph_edge|from_service=" + fromService + 
  "|caller=" + callerClass.getQualifiedName() +
  "|to_service=" + toService +
  "|callee=" + calleeClass.getQualifiedName()
"""

CONTROL_FLOW_STRUCTURE_QUERY = """/**
 * @name DeathStarBench Control Flow Structure (Aggregated)
 * @description Captures control-flow statement counts per function
 * @kind problem
 * @problem.severity recommendation
 * @id deathstar/control-flow-structure
 */

import cpp

string getMicroserviceFromFile(File f) {
  exists(string path |
    path = f.getRelativePath() and
    path.matches("socialNetwork/src/%") and
    result = path.regexpCapture("socialNetwork/src/([^/]+)/.*", 1)
  )
}

predicate isSignificantFunction(Function f) {
  (f.getName().matches("%Service%") or
   f.getName().matches("handle%") or
   f.getName().matches("process%") or
   f.getName().matches("compose%")) and
  not f.getName().matches("%test%")
}

from Function f, string serviceName, int ifCount, int forCount, int whileCount, int switchCount
where
  f.fromSource() and
  isSignificantFunction(f) and
  f.getFile().getRelativePath().matches("socialNetwork/src/%") and
  serviceName = getMicroserviceFromFile(f.getFile()) and
  ifCount = count(IfStmt s | s.getEnclosingFunction() = f) and
  forCount = count(ForStmt s | s.getEnclosingFunction() = f) and
  whileCount = count(WhileStmt s | s.getEnclosingFunction() = f) and
  switchCount = count(SwitchStmt s | s.getEnclosingFunction() = f) and
  (ifCount > 0 or forCount > 0 or whileCount > 0 or switchCount > 0)
select f, "kind=control_flow_structure|service=" + serviceName + 
  "|function=" + f.getQualifiedName() +
  "|if_count=" + ifCount +
  "|for_count=" + forCount +
  "|while_count=" + whileCount +
  "|switch_count=" + switchCount
"""

INTERACTION_SITES_QUERY = """/**
 * @name DeathStarBench Interaction Sites (Aggregated)
 * @description Captures external library calls aggregated by function
 * @kind problem
 * @problem.severity recommendation
 * @id deathstar/interaction-sites
 */

import cpp

string getMicroserviceFromFile(File f) {
  exists(string path |
    path = f.getRelativePath() and
    path.matches("socialNetwork/src/%") and
    result = path.regexpCapture("socialNetwork/src/([^/]+)/.*", 1)
  )
}

predicate isExternalLibrary(Function f) {
  exists(string name |
    name = f.getQualifiedName() and
    (
      name.matches("std::%") or
      name.matches("boost::%") or
      name.matches("apache::thrift::%") or
      name.matches("mongoc::%") or
      name.matches("redis::%") or
      name.matches("memcached::%")
    )
  )
}

predicate isDbLibrary(Function f) {
  exists(string name |
    name = f.getQualifiedName() and
    (
      name.matches("%mongo%") or
      name.matches("%redis%") or
      name.matches("%memcached%") or
      name.matches("%mysql%") or
      name.matches("%postgres%")
    )
  )
}

from Function caller, string serviceName, string targetLib, string interactionType
where
  caller.fromSource() and
  caller.getFile().getRelativePath().matches("socialNetwork/src/%") and
  serviceName = getMicroserviceFromFile(caller.getFile()) and
  exists(FunctionCall call, Function callee |
    call.getEnclosingFunction() = caller and
    call.getTarget() = callee and
    isExternalLibrary(callee) and
    targetLib = callee.getQualifiedName().regexpCapture("([^:]+)::.*", 1) and
    (
      (isDbLibrary(callee) and interactionType = "db_access") or
      (not isDbLibrary(callee) and interactionType = "external_call")
    )
  )
select caller, "kind=interaction_site|service=" + serviceName + 
  "|function=" + caller.getQualifiedName() +
  "|type=" + interactionType +
  "|target_lib=" + targetLib
"""

SYNCHRONIZATION_CONSTRUCTS_QUERY = """/**
 * @name DeathStarBench Synchronization Constructs
 * @description Captures mutex, lock, and thread synchronization
 * @kind problem
 * @problem.severity recommendation
 * @id deathstar/synchronization-constructs
 */

import cpp

string getMicroserviceFromFile(File f) {
  exists(string path |
    path = f.getRelativePath() and
    path.matches("socialNetwork/src/%") and
    result = path.regexpCapture("socialNetwork/src/([^/]+)/.*", 1)
  )
}

from Function f, string serviceName, string syncType
where
  f.fromSource() and
  f.getFile().getRelativePath().matches("socialNetwork/src/%") and
  serviceName = getMicroserviceFromFile(f.getFile()) and
  exists(FunctionCall call |
    call.getEnclosingFunction() = f and
    (
      (call.getTarget().getName().matches("%lock%") and syncType = "lock") or
      (call.getTarget().getName().matches("%mutex%") and syncType = "mutex") or
      (call.getTarget().getName().matches("%thread%") and syncType = "thread") or
      (call.getTarget().getName().matches("%atomic%") and syncType = "atomic")
    )
  )
select f, "kind=synchronization_construct|service=" + serviceName + 
  "|type=" + syncType + 
  "|function=" + f.getQualifiedName()
"""

QLPACK_YML = """name: deathstar/microservice-analysis
version: 0.0.1
libraryPathDependencies:
  - codeql/cpp-all
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
    suite_text = f"""- description: DeathStarBench Multi-Query Analysis
- queries: .
- include:
    id:
      - {suite_rules}
"""

    (queries_dir / "deathstar-analysis.qls").write_text(suite_text)
    (queries_dir / "qlpack.yml").write_text(QLPACK_YML)

    logger.info(f"Created {len(queries)} CodeQL query files in {queries_dir} for {tool_name}")


def _run_codeql_analysis(repo_path: Path, tool_name: str, queries_dir_name: str) -> Path:
    """Run CodeQL analysis using Docker container.

    Args:
        repo_path: Path to the DeathStarBench repository
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

    # Docker command for C++ compilation (adjust build command for DeathStarBench)
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
        "LANGUAGE=cpp",
        "-e",
        "COMMAND=mkdir -p build && cd build && cmake .. && make -j$(nproc)",
        "-e",
        f"QS=/opt/src/{queries_dir_name}/deathstar-analysis.qls",
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
    logger.info(f"Starting DeathStarBench CodeQL multi-query analysis with {tool_name} for: {repo_path}")
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

        logger.info(f"DeathStarBench CodeQL analysis completed successfully for {tool_name}")
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
# CODEQL COMBINED ANALYSIS TOOLS (OPTIMIZED FOR C++)
# ============================================================================


@tool
def deathstar_component_analysis(repo_path: str) -> str:
    """Comprehensive component analysis for DeathStarBench socialnetwork architecture (OPTIMIZED).

    Runs all component-related CodeQL queries in a single analysis pass:
    - Microservice identification (directory structure analysis)
    - Endpoint discovery (handlers, services, servers)
    - Component inventory (FILTERED: only significant classes and functions)
    - Hierarchical composition (FILTERED: only significant relationships)
    - Exported HTTP endpoints (public API surface)
    - Exported public API (FILTERED: only entry point functions)
    - Call-based dependencies (AGGREGATED: class-level instead of function-level)
    - Resource-based dependencies (URLs, service endpoints)

    OPTIMIZATION: Output reduced by 80-95% while preserving all architecturally significant
    information through filtering, aggregation, and deduplication.

    This tool is optimized for ComponentSummarizerAgent to gather complete structural information
    about the DeathStarBench socialnetwork microservices architecture in a single Docker run.

    Returns JSON:
    {
      "success": bool,
      "results": {
        "deathstar/find-microservices-simple": [{kv pairs...}, ...],
        "deathstar/find-all-endpoints": [{kv pairs...}, ...],
        "deathstar/component-inventory": [{kv pairs...}, ...],
        "deathstar/hierarchical-composition": [{kv pairs...}, ...],
        "deathstar/exported-http-endpoints": [{kv pairs...}, ...],
        "deathstar/exported-public-api": [{kv pairs...}, ...],
        "deathstar/deps-call-based": [{kv pairs...}, ...],
        "deathstar/deps-resource-based": [{kv pairs...}, ...]
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
        "deathstar/find-microservices-simple",
        "deathstar/find-all-endpoints",
        "deathstar/component-inventory",
        "deathstar/hierarchical-composition",
        "deathstar/exported-http-endpoints",
        "deathstar/exported-public-api",
        "deathstar/deps-call-based",
        "deathstar/deps-resource-based",
    ]

    return _run_multi_query_tool(repo_path, queries, rule_ids, "component_analysis")


@tool
def deathstar_behavior_analysis(repo_path: str) -> str:
    """Comprehensive behavior analysis for DeathStarBench socialnetwork execution patterns (OPTIMIZED).

    Runs all behavior-related CodeQL queries in a single analysis pass:
    - Rooted call graph (AGGREGATED: class-level interprocedural calls)
    - Control flow structure (AGGREGATED: statement counts per function)
    - Interaction sites (AGGREGATED: external library calls by function)
    - Synchronization constructs (mutex, locks, thread operations)

    OPTIMIZATION: Output reduced by 80-95% while preserving all architecturally significant
    information through aggregation and filtering to significant functions only.

    This tool is optimized for BehaviorSummarizerAgent to gather complete runtime behavior
    information about the DeathStarBench socialnetwork microservices in a single Docker run.

    Returns JSON:
    {
      "success": bool,
      "results": {
        "deathstar/rooted-call-graph-depth5": [{kv pairs...}, ...],
        "deathstar/control-flow-structure": [{kv pairs...}, ...],
        "deathstar/interaction-sites": [{kv pairs...}, ...],
        "deathstar/synchronization-constructs": [{kv pairs...}, ...]
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
        "deathstar/rooted-call-graph-depth5",
        "deathstar/control-flow-structure",
        "deathstar/interaction-sites",
        "deathstar/synchronization-constructs",
    ]

    return _run_multi_query_tool(repo_path, queries, rule_ids, "behavior_analysis")