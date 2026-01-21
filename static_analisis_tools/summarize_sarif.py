import json
import collections
import os
from pathlib import Path

# Use environment variables for Docker compatibility
OUTPUT_BASE = Path(os.getenv("CODEQL_OUTPUT", "./output"))
OUTPUT_JSON = OUTPUT_BASE / "output.json"

# Detect project name from output directory path
PROJECT_NAME = OUTPUT_BASE.name if OUTPUT_BASE.name != "output" else "CodeQL Analysis"

def main():
    sarif_files = sorted(OUTPUT_BASE.glob("*.sarif"))
    if not sarif_files:
        print(f"Error: No SARIF files found in {OUTPUT_BASE}")
        return

    # Process all SARIF files
    all_results = []
    rule_map = {}

    for sarif_file in sarif_files:
        print(f"Processing {sarif_file.name}...")
        try:
            with open(sarif_file, 'r') as f:
                data = json.load(f)
                runs = data.get('runs', [])
                for run in runs:
                    results = run.get('results', [])
                    tool = run.get('tool', {})
                    driver = tool.get('driver', {})
                    rules = driver.get('rules', [])
                    
                    all_results.extend(results)
                    for r in rules:
                        rule_map[r['id']] = r
                        
        except Exception as e:
            print(f"Failed to read {sarif_file}: {e}")

    # Group results by Rule ID
    grouped = collections.defaultdict(list)
    for res in all_results:
        rule_id = res.get('ruleId') or 'Unknown'
        grouped[rule_id].append(res)

    # Sort by count (descending), then rule id for stability
    sorted_rules = sorted(
        grouped.items(),
        key=lambda item: (-len(item[1]), item[0])
    )

    rules = []
    for rule_id, findings in sorted_rules:
        rule_info = rule_map.get(rule_id, {})
        short_desc = rule_info.get('shortDescription', {}).get('text', rule_id)
        full_desc = rule_info.get('fullDescription', {}).get('text', '')
        severity = rule_info.get('defaultConfiguration', {}).get('level', 'warning')

        rule_entry = {
            "ruleId": rule_id,
            "shortDescription": short_desc,
            "fullDescription": full_desc,
            "severity": severity,
            "count": len(findings),
            "findings": [],
        }

        for finding in findings:
            msg = finding.get('message', {}).get('text', 'No description')
            locations = []
            for loc in finding.get('locations', []):
                phys_loc = loc.get('physicalLocation', {})
                uri = phys_loc.get('artifactLocation', {}).get('uri', 'unknown file')
                display_path = uri.split('src/', 1)[-1] if 'src/' in uri else uri
                line = phys_loc.get('region', {}).get('startLine')
                locations.append({
                    "path": display_path,
                    "line": line,
                    "uri": uri,
                })

            rule_entry["findings"].append({
                "message": msg,
                "locations": locations,
            })

        rules.append(rule_entry)

    report = {
        "project": PROJECT_NAME,
        "summary": {
            "totalAlerts": len(all_results),
            "rulesScanned": len(rule_map),
        },
        "sarifFiles": [f.name for f in sarif_files],
        "rules": rules,
    }

    # Write to file
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(report, f, indent=2, sort_keys=False)

    print(f"Report generated at: {OUTPUT_JSON}")

if __name__ == '__main__':
    main()
