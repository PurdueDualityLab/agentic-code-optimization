"""Native dependency analyzer for multiple ecosystems."""

from __future__ import annotations

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List

from .utils import normalize_path, safe_run, which


class NativeDependencyAnalyzer:
    """Analyze dependencies using native package manager files or CLIs."""

    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path).resolve()

    def analyze(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "dependencies": {},
            "project_types": [],
        }

        if self._has_dotnet_projects():
            results["project_types"].append("dotnet")
            results["dependencies"]["nuget"] = self._analyze_dotnet()

        if self._has_npm_projects():
            results["project_types"].append("npm")
            results["dependencies"]["npm"] = self._analyze_npm()

        if self._has_go_projects():
            results["project_types"].append("go")
            results["dependencies"]["go"] = self._analyze_go()

        if self._has_maven_projects():
            results["project_types"].append("maven")
            results["dependencies"]["maven"] = self._analyze_maven()

        if self._has_gradle_projects():
            results["project_types"].append("gradle")
            results["dependencies"]["gradle"] = self._analyze_gradle()

        return results

    def _has_dotnet_projects(self) -> bool:
        return any(self.root_path.rglob("*.csproj"))

    def _has_npm_projects(self) -> bool:
        return any(self.root_path.rglob("package.json"))

    def _has_go_projects(self) -> bool:
        return any(self.root_path.rglob("go.mod"))

    def _has_maven_projects(self) -> bool:
        return any(self.root_path.rglob("pom.xml"))

    def _has_gradle_projects(self) -> bool:
        return any(self.root_path.rglob("build.gradle")) or any(self.root_path.rglob("build.gradle.kts"))

    def _analyze_dotnet(self) -> List[Dict[str, Any]]:
        dependencies: List[Dict[str, Any]] = []
        csproj_files = list(self.root_path.rglob("*.csproj"))

        if which("dotnet"):
            for csproj in csproj_files:
                code, stdout, _stderr = safe_run(
                    ["dotnet", "list", str(csproj), "package", "--format", "json"],
                    timeout=30,
                    cwd=self.root_path,
                )
                if code != 0:
                    continue
                try:
                    data = json.loads(stdout)
                except json.JSONDecodeError:
                    continue
                for project in data.get("projects", []):
                    for framework in project.get("frameworks", []):
                        for pkg in framework.get("topLevelPackages", []):
                            dependencies.append({
                                "name": pkg.get("id"),
                                "version": pkg.get("resolvedVersion") or pkg.get("requestedVersion"),
                                "project": normalize_path(csproj, self.root_path),
                            })
            return dependencies

        for csproj in csproj_files:
            try:
                tree = ET.parse(csproj)
                root = tree.getroot()
                for package_ref in root.findall(".//PackageReference"):
                    name = package_ref.attrib.get("Include")
                    version = package_ref.attrib.get("Version") or "unknown"
                    if name:
                        dependencies.append({
                            "name": name,
                            "version": version,
                            "project": normalize_path(csproj, self.root_path),
                        })
            except Exception:
                continue

        return dependencies

    def _analyze_npm(self) -> List[Dict[str, Any]]:
        dependencies: List[Dict[str, Any]] = []
        for package_json in self.root_path.rglob("package.json"):
            if "node_modules" in str(package_json):
                continue
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
                for name, version in data.get("dependencies", {}).items():
                    dependencies.append({
                        "name": name,
                        "version": version,
                        "type": "runtime",
                        "project": normalize_path(package_json, self.root_path),
                    })
                for name, version in data.get("devDependencies", {}).items():
                    dependencies.append({
                        "name": name,
                        "version": version,
                        "type": "dev",
                        "project": normalize_path(package_json, self.root_path),
                    })
            except Exception:
                continue

        return dependencies

    def _analyze_go(self) -> List[Dict[str, Any]]:
        dependencies: List[Dict[str, Any]] = []
        go_mods = list(self.root_path.rglob("go.mod"))

        if which("go"):
            for go_mod in go_mods:
                code, stdout, _stderr = safe_run(
                    ["go", "list", "-m", "-json", "all"],
                    timeout=30,
                    cwd=go_mod.parent,
                )
                if code != 0:
                    continue
                for line in stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        mod = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    dependencies.append({
                        "name": mod.get("Path"),
                        "version": mod.get("Version", "unknown"),
                        "project": normalize_path(go_mod, self.root_path),
                    })
            return dependencies

        for go_mod in go_mods:
            try:
                content = go_mod.read_text(encoding="utf-8", errors="ignore")
                in_require = False
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("require"):
                        in_require = True
                        continue
                    if in_require:
                        if line.startswith("("):
                            continue
                        if line.startswith(")"):
                            break
                        parts = line.split()
                        if len(parts) >= 2:
                            dependencies.append({
                                "name": parts[0],
                                "version": parts[1],
                                "project": normalize_path(go_mod, self.root_path),
                            })
            except Exception:
                continue

        return dependencies

    def _analyze_maven(self) -> List[Dict[str, Any]]:
        dependencies: List[Dict[str, Any]] = []
        for pom in self.root_path.rglob("pom.xml"):
            try:
                tree = ET.parse(pom)
                root = tree.getroot()
                ns = {"maven": "http://maven.apache.org/POM/4.0.0"}
                for dep in root.findall(".//maven:dependency", ns):
                    group_id = dep.find("maven:groupId", ns)
                    artifact_id = dep.find("maven:artifactId", ns)
                    version = dep.find("maven:version", ns)
                    if group_id is not None and artifact_id is not None:
                        dependencies.append({
                            "name": f"{group_id.text}:{artifact_id.text}",
                            "version": version.text if version is not None else "unknown",
                            "project": normalize_path(pom, self.root_path),
                        })
            except Exception:
                continue

        return dependencies

    def _analyze_gradle(self) -> List[Dict[str, Any]]:
        dependencies: List[Dict[str, Any]] = []
        for build_file in list(self.root_path.rglob("build.gradle")) + list(self.root_path.rglob("build.gradle.kts")):
            try:
                content = build_file.read_text(encoding="utf-8", errors="ignore")
                patterns = [
                    r"implementation\s+['\"]([^:]+):([^:]+):([^'\"]+)['\"]",
                    r"compile\s+['\"]([^:]+):([^:]+):([^'\"]+)['\"]",
                ]
                for pattern in patterns:
                    for match in re.finditer(pattern, content):
                        dependencies.append({
                            "name": f"{match.group(1)}:{match.group(2)}",
                            "version": match.group(3),
                            "project": normalize_path(build_file, self.root_path),
                        })
            except Exception:
                continue

        return dependencies
