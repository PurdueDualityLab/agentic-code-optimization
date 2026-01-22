# TeaStore CodeQL Queries for Manual Testing

This directory contains all CodeQL queries used by the `tools/codeql.py` module for analyzing TeaStore microservices architecture.

## Directory Structure

```
codeql-queries/
├── README.md                           # This file
├── qlpack.yml                          # CodeQL package configuration
├── component-analysis.qls              # Component analysis query suite
├── behavior-analysis.qls               # Behavior analysis query suite
│
├── Component Analysis Queries (8 queries):
│   ├── find-microservices.ql          # Identify microservices by package structure
│   ├── find-endpoints.ql              # Find HTTP endpoints (servlets, REST, controllers)
│   ├── component-inventory.ql         # List significant packages and classes
│   ├── hierarchical-composition.ql    # Package-to-class and inheritance relationships
│   ├── exported-http-endpoints.ql     # HTTP endpoint classes
│   ├── exported-public-api.ql         # Public entry point methods
│   ├── deps-call-based.ql            # Class-to-class call dependencies
│   └── deps-resource-based.ql        # Resource references (URLs, file paths)
│
└── Behavior Analysis Queries (4 queries):
    ├── rooted-call-graph-depth5.ql    # Interprocedural call graph (class-level)
    ├── control-flow-structure.ql      # Control flow statement counts per class
    ├── interaction-sites.ql           # External calls and database access
    └── synchronization-constructs.ql  # Synchronized methods and blocks
```

## Prerequisites

1. **CodeQL CLI**: Install from https://github.com/github/codeql-cli-binaries
2. **Java CodeQL Library**: Downloaded automatically by CodeQL
3. **TeaStore Repository**: Clone from https://github.com/DescartesResearch/TeaStore

## Manual Testing with CodeQL CLI

### Option 1: Run Individual Query

```bash
# Navigate to TeaStore repository
cd /path/to/TeaStore

# Create CodeQL database (one-time setup)
codeql database create teastore-db \
  --language=java \
  --command="mvn clean compile -DskipTests"

# Run a single query
codeql query run \
  /path/to/codeql-queries/find-microservices.ql \
  --database=teastore-db \
  --output=results.sarif

# View results in human-readable format
codeql bqrs decode results.bqrs --format=text
```

### Option 2: Run Component Analysis Suite

```bash
# Navigate to TeaStore repository
cd /path/to/TeaStore

# Create database (if not already created)
codeql database create teastore-db \
  --language=java \
  --command="mvn clean compile -DskipTests"

# Run all component analysis queries
codeql database analyze teastore-db \
  /path/to/codeql-queries/component-analysis.qls \
  --format=sarif-latest \
  --output=component-results.sarif

# Convert SARIF to readable format
codeql bqrs decode component-results.bqrs --format=text
```

### Option 3: Run Behavior Analysis Suite

```bash
# Navigate to TeaStore repository
cd /path/to/TeaStore

# Create database (if not already created)
codeql database create teastore-db \
  --language=java \
  --command="mvn clean compile -DskipTests"

# Run all behavior analysis queries
codeql database analyze teastore-db \
  /path/to/codeql-queries/behavior-analysis.qls \
  --format=sarif-latest \
  --output=behavior-results.sarif

# Convert SARIF to readable format
codeql bqrs decode behavior-results.bqrs --format=text
```

## Using with Docker (codeql-agent)

The `tools/codeql.py` module uses a Docker image called `codeql-agent` that wraps CodeQL CLI. To replicate this:

### Step 1: Copy queries to TeaStore repo

```bash
# Copy this entire directory to TeaStore repository
cp -r codeql-queries /path/to/TeaStore/

cd /path/to/TeaStore
```

### Step 2: Run with Docker (if codeql-agent image is available)

```bash
# Create results directory
mkdir -p codeql-results

# Run component analysis
docker run --rm \
  -v $(pwd):/opt/src \
  -v $(pwd)/codeql-results:/opt/results \
  -e LANGUAGE=java \
  -e COMMAND="mvn clean compile -DskipTests -pl !utilities/tools.descartes.teastore.docker.all" \
  -e QS=/opt/src/codeql-queries/component-analysis.qls \
  codeql-agent

# Results will be in codeql-results/issues.sarif
```

## Query Output Format

All queries use a key-value encoded output format for easy parsing:

```
kind=microservice|service=webui|component_fqn=tools.descartes.teastore.webui.servlet.IndexServlet
kind=endpoint|service=auth|endpoint_fqn=tools.descartes.teastore.auth.rest.AuthEndpoint
kind=call_dependency|from_service=webui|from_class=...Servlet|to_service=auth|to_class=...Client
```

This format is parsed by `_parse_kv_message()` in `tools/codeql.py`.

## Query Descriptions

### Component Analysis Queries

1. **find-microservices.ql** - Identifies TeaStore microservices (webui, auth, persistence, recommender, image, registry) by analyzing package structure and significant component classes.

2. **find-endpoints.ql** - Finds all HTTP endpoint classes based on naming conventions (Servlet, Endpoint, Rest, Controller suffixes).

3. **component-inventory.ql** - Lists significant components including top-level service packages and important classes (services, endpoints, repositories, managers).

4. **hierarchical-composition.ql** - Captures hierarchical relationships: package-to-class containment and class inheritance.

5. **exported-http-endpoints.ql** - Identifies classes that expose HTTP endpoints for external access.

6. **exported-public-api.ql** - Lists all public methods in entry point classes (endpoints, servlets, services).

7. **deps-call-based.ql** - Captures inter-class call dependencies by analyzing method calls.

8. **deps-resource-based.ql** - Finds resource references like HTTP URLs and API paths in string literals.

### Behavior Analysis Queries

1. **rooted-call-graph-depth5.ql** - Builds interprocedural call graph at class level, showing which classes call which other classes.

2. **control-flow-structure.ql** - Counts control flow constructs (if, for, while, switch) in each significant class.

3. **interaction-sites.ql** - Identifies external interactions: database access and calls to external libraries.

4. **synchronization-constructs.ql** - Finds synchronized methods that may indicate concurrency patterns.

## Filtering and Optimization

The queries are optimized to reduce output volume while preserving architectural information:

- **Filtered Classes**: Only significant classes (endpoints, services, repositories, managers, handlers) are analyzed
- **Aggregated Results**: Many queries aggregate at class level rather than method level
- **Deduplication**: The `_parse_sarif_multi()` function in `tools/codeql.py` deduplicates results

## Integration with Agents

These queries are used by:

1. **ComponentSummarizerAgent** (`agents/summarizers/component.py`)
   - Uses: `component-analysis.qls` (8 queries)
   - Tool: `teastore_component_analysis()`

2. **BehaviorSummarizerAgent** (`agents/summarizers/behavior.py`)
   - Uses: `behavior-analysis.qls` (4 queries)
   - Tool: `teastore_behavior_analysis()`

## Troubleshooting

### Database creation fails

```bash
# Ensure Maven build succeeds first
cd /path/to/TeaStore
mvn clean compile -DskipTests

# Then create database
codeql database create teastore-db --language=java --command="mvn compile -DskipTests"
```

### Query returns no results

- Verify TeaStore is in the expected package structure (`tools.descartes.teastore.*`)
- Check that the database was created successfully
- Ensure you're running against a TeaStore codebase, not another Java project

### SARIF output is too large

- Use individual queries instead of suites
- The queries are already optimized to filter results
- Use `--max-results` flag with CodeQL CLI to limit output

## Example Results

### Microservices Found
```
service=webui, component_fqn=tools.descartes.teastore.webui.servlet.IndexServlet
service=auth, component_fqn=tools.descartes.teastore.auth.security.BCryptProvider
service=persistence, component_fqn=tools.descartes.teastore.persistence.rest.PersistenceEndpoint
service=recommender, component_fqn=tools.descartes.teastore.recommender.algorithm.RecommendAlgorithm
service=image, component_fqn=tools.descartes.teastore.image.rest.ImageEndpoint
service=registry, component_fqn=tools.descartes.teastore.registry.rest.RegistryRest
```

### Call Dependencies
```
from_service=webui|from_class=...IndexServlet|to_service=recommender|to_class=...RecommendClient
from_service=persistence|from_class=...PersistenceEndpoint|to_service=registry|to_class=...RegistryClient
```

## References

- TeaStore GitHub: https://github.com/DescartesResearch/TeaStore
- CodeQL Documentation: https://codeql.github.com/docs/
- CodeQL for Java: https://codeql.github.com/docs/codeql-language-guides/codeql-for-java/
- SARIF Format: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
