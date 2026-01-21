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
select c, "Microservice component: " + serviceName + " - " + c.getQualifiedName()
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
  // Get microservice name
  serviceName = getMicroserviceFromPackage(c.getPackage()) and
  // From source code (not libraries)
  c.fromSource()
select c, "Endpoint in " + serviceName + ": " + c.getQualifiedName()
"""

QUERY_SUITE = """- description: TeaStore Microservices Analysis
- queries: .
- include:
    id:
      - teastore/find-microservices-simple
      - teastore/find-all-endpoints
"""

QLPACK_YML = """name: teastore/microservice-analysis
version: 0.0.1
libraryPathDependencies:
  - codeql/java-all
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _create_query_files(queries_dir: Path) -> None:
    """Write CodeQL query files to the specified directory.

    Args:
        queries_dir: Directory where query files should be written
    """
    queries_dir.mkdir(parents=True, exist_ok=True)

    # Write query files
    (queries_dir / "find-microservices-simple.ql").write_text(FIND_MICROSERVICES_QUERY)
    (queries_dir / "find-all-endpoints.ql").write_text(FIND_ENDPOINTS_QUERY)
    (queries_dir / "teastore-analysis.qls").write_text(QUERY_SUITE)
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
        result = subprocess.run(
            docker_cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info("CodeQL analysis completed successfully")
        logger.debug(f"Docker output: {result.stdout}")

        sarif_path = repo_path / "codeql-agent-results" / "issues.sarif"
        if not sarif_path.exists():
            raise RuntimeError(f"SARIF results file not found at {sarif_path}")

        return sarif_path

    except subprocess.CalledProcessError as e:
        logger.error(f"Docker command failed: {e.stderr}")
        raise RuntimeError(f"CodeQL analysis failed: {e.stderr}")


def _parse_sarif_results(sarif_path: Path) -> dict[str, list[str]]:
    """Parse SARIF results file and extract component names.

    Args:
        sarif_path: Path to SARIF results file

    Returns:
        Dictionary with 'endpoints' and 'microservices' keys containing component names
    """
    logger.info(f"Parsing SARIF results from {sarif_path}")

    with open(sarif_path) as f:
        sarif_data = json.load(f)

    endpoints = set()
    microservices = set()

    # Extract results from SARIF
    for run in sarif_data.get("runs", []):
        for result in run.get("results", []):
            rule_id = result.get("ruleId", "")
            message_text = result.get("message", {}).get("text", "")

            # Parse based on query ID
            if rule_id == "teastore/find-all-endpoints":
                # Extract endpoint name from message
                # Format: "Endpoint in {service}: {qualified_name}"
                if ":" in message_text:
                    qualified_name = message_text.split(":")[-1].strip()
                    # Get class name (last part of qualified name)
                    class_name = qualified_name.split(".")[-1]
                    endpoints.add(class_name)

            elif rule_id == "teastore/find-microservices-simple":
                # Extract microservice name from message
                # Format: "Microservice component: {service} - {qualified_name}"
                if " - " in message_text:
                    parts = message_text.split(" - ")
                    if len(parts) == 2:
                        service_part = parts[0].replace("Microservice component:", "").strip()
                        microservices.add(service_part)

    logger.info(
        f"Parsed {len(endpoints)} unique endpoints and {len(microservices)} unique microservices"
    )

    return {
        "endpoints": sorted(list(endpoints)),
        "microservices": sorted(list(microservices)),
    }


def _cleanup_analysis_files(repo_path: Path) -> None:
    """Remove temporary CodeQL analysis files and directories.

    Args:
        repo_path: Path to the repository where analysis files were created
    """
    logger.info("Cleaning up CodeQL analysis files...")

    # Remove codeql-queries folder
    queries_dir = repo_path / "codeql-queries"
    if queries_dir.exists():
        try:
            shutil.rmtree(queries_dir)
            logger.info(f"Removed {queries_dir}")
        except Exception as e:
            logger.warning(f"Failed to remove {queries_dir}: {e}")

    # Remove codeql-agent-results folder
    results_dir = repo_path / "codeql-agent-results"
    if results_dir.exists():
        try:
            shutil.rmtree(results_dir)
            logger.info(f"Removed {results_dir}")
        except Exception as e:
            logger.warning(f"Failed to remove {results_dir}: {e}")


# ============================================================================
# CODEQL ANALYSIS TOOL
# ============================================================================


@tool
def teastore_codeql_analyzer(repo_path: str) -> str:
    """Analyze TeaStore microservices architecture using CodeQL.

    This is a hardcoded tool specifically designed for TeaStore benchmark repositories.
    It runs CodeQL queries to identify microservices and endpoints in the TeaStore codebase.

    The tool performs the following steps:
    1. Creates a codeql-queries folder in the repository
    2. Writes CodeQL query files (find-microservices-simple.ql, find-all-endpoints.ql)
    3. Runs CodeQL analysis via Docker container
    4. Parses SARIF results to extract component names
    5. Cleans up temporary files (codeql-queries/ and codeql-agent-results/)
    6. Returns a structured map of endpoints and microservices

    Note: All temporary files created during analysis are automatically cleaned up before returning,
    leaving the repository in its original state.

    Args:
        repo_path: Absolute path to the TeaStore repository root directory

    Returns:
        JSON string containing:
        - endpoints: List of endpoint class names (sorted)
        - microservices: List of microservice names (sorted)
        - total_findings: Total number of CodeQL findings
        - success: Boolean indicating if analysis completed successfully

    Example:
        >>> result = teastore_codeql_analyzer("/path/to/TeaStore")
        >>> data = json.loads(result)
        >>> data["microservices"]
        ["auth", "image", "persistence", "recommender", "registry", "webui"]
        >>> len(data["endpoints"])
        36

    Raises:
        RuntimeError: If CodeQL analysis fails or SARIF results cannot be parsed
    """
    logger.info(f"Starting TeaStore CodeQL analysis for: {repo_path}")

    try:
        repo_path_obj = Path(repo_path).resolve()

        # Validate repository path
        if not repo_path_obj.exists():
            error_msg = f"Repository path does not exist: {repo_path}"
            logger.error(error_msg)
            return json.dumps(
                {"success": False, "error": error_msg, "endpoints": [], "microservices": []},
                indent=2,
            )

        # Step 1: Create query files
        queries_dir = repo_path_obj / "codeql-queries"
        _create_query_files(queries_dir)

        # Step 2: Run CodeQL analysis
        sarif_path = _run_codeql_analysis(repo_path_obj)

        # Step 3: Parse results
        components = _parse_sarif_results(sarif_path)

        # Step 4: Prepare structured results
        result = {
            "success": True,
            "endpoints": components["endpoints"],
            "microservices": components["microservices"],
            "total_findings": len(components["endpoints"]) + len(components["microservices"]),
        }

        # Step 5: Clean up temporary files
        _cleanup_analysis_files(repo_path_obj)

        logger.info("TeaStore CodeQL analysis completed successfully")
        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"CodeQL analysis failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Clean up any created files even on failure
        try:
            _cleanup_analysis_files(repo_path_obj)
        except Exception as cleanup_error:
            logger.warning(f"Cleanup failed after error: {cleanup_error}")

        return json.dumps(
            {"success": False, "error": error_msg, "endpoints": [], "microservices": []},
            indent=2,
        )
