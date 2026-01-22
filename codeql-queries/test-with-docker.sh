#!/bin/bash
# Test script for running CodeQL queries with codeql-agent Docker container
#
# Usage: ./test-with-docker.sh /path/to/TeaStore [component|behavior]
#
# This script demonstrates how tools/codeql.py runs CodeQL analysis

set -e

# Configuration
TEASTORE_PATH="${1:-../Benchmarks/TeaStore}"
ANALYSIS_TYPE="${2:-component}"  # component or behavior
QUERY_SUITE="${ANALYSIS_TYPE}-analysis.qls"

# Validate inputs
if [ ! -d "$TEASTORE_PATH" ]; then
    echo "Error: TeaStore path not found: $TEASTORE_PATH"
    echo "Usage: $0 /path/to/TeaStore [component|behavior]"
    exit 1
fi

if [ "$ANALYSIS_TYPE" != "component" ] && [ "$ANALYSIS_TYPE" != "behavior" ]; then
    echo "Error: Analysis type must be 'component' or 'behavior'"
    echo "Usage: $0 /path/to/TeaStore [component|behavior]"
    exit 1
fi

# Resolve paths
TEASTORE_ABS=$(cd "$TEASTORE_PATH" && pwd)
QUERIES_DIR=$(pwd)

echo "═══════════════════════════════════════════════════════════════"
echo "CodeQL Analysis Test"
echo "═══════════════════════════════════════════════════════════════"
echo "TeaStore path:  $TEASTORE_ABS"
echo "Query suite:    $QUERY_SUITE"
echo "Container name: codeql-test-${ANALYSIS_TYPE}"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Copy queries to TeaStore repository
echo "1. Copying queries to TeaStore repository..."
cp -r "$QUERIES_DIR" "$TEASTORE_ABS/codeql-queries-test"

# Create results directory
mkdir -p "$TEASTORE_ABS/codeql-results-test"

echo "2. Running CodeQL analysis via Docker..."
echo "   (This will compile TeaStore and run CodeQL queries)"
echo ""

# Run Docker container (matching tools/codeql.py behavior)
docker run --rm \
    --name "codeql-test-${ANALYSIS_TYPE}" \
    -v "$TEASTORE_ABS:/opt/src" \
    -v "$TEASTORE_ABS/codeql-results-test:/opt/results" \
    -e LANGUAGE=java \
    -e COMMAND="mvn clean compile -DskipTests -pl !utilities/tools.descartes.teastore.docker.all" \
    -e QS="/opt/src/codeql-queries-test/${QUERY_SUITE}" \
    codeql-agent

echo ""
echo "3. Analysis complete!"
echo ""
echo "Results saved to:"
echo "  $TEASTORE_ABS/codeql-results-test/issues.sarif"
echo ""

# Parse and display results
if [ -f "$TEASTORE_ABS/codeql-results-test/issues.sarif" ]; then
    echo "4. Parsing results..."

    # Count findings per rule
    python3 << 'EOF'
import json
import sys
from pathlib import Path

sarif_path = Path(sys.argv[1])
with open(sarif_path) as f:
    sarif = json.load(f)

print("\n═══════════════════════════════════════════════════════════════")
print("Results Summary")
print("═══════════════════════════════════════════════════════════════")

rule_counts = {}
total = 0

for run in sarif.get("runs", []):
    for result in run.get("results", []):
        rule_id = result.get("ruleId", "unknown")
        rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1
        total += 1

for rule_id in sorted(rule_counts.keys()):
    count = rule_counts[rule_id]
    print(f"{rule_id:50s} : {count:5d} findings")

print("─" * 67)
print(f"{'TOTAL':50s} : {total:5d} findings")
print("═══════════════════════════════════════════════════════════════")
print()
print("Sample findings (first 5):")
print()

sample_count = 0
for run in sarif.get("runs", []):
    for result in run.get("results", []):
        if sample_count >= 5:
            break
        rule_id = result.get("ruleId", "unknown")
        message = result.get("message", {}).get("text", "")
        print(f"[{rule_id}]")
        print(f"  {message}")
        print()
        sample_count += 1

EOF
python3 -c "$(cat)" "$TEASTORE_ABS/codeql-results-test/issues.sarif"
fi

# Cleanup
echo "5. Cleaning up temporary files..."
rm -rf "$TEASTORE_ABS/codeql-queries-test"
rm -rf "$TEASTORE_ABS/codeql-results-test"

echo "✓ Done!"
echo ""
echo "To view full SARIF results, run analysis again and examine:"
echo "  $TEASTORE_ABS/codeql-results-test/issues.sarif"
