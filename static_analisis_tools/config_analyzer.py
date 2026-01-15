"""Configuration and deployment file static analyzer."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency
    yaml = None

from .base import StaticAnalyzer
from .utils import normalize_path


class ConfigAnalyzer(StaticAnalyzer):
    """Analyzer for configuration and deployment files."""

    def analyze(self) -> Dict[str, Any]:
        self.results = {
            "dockerfiles": self.parse_dockerfiles(),
            "docker_compose": self.parse_compose_files(),
            "kubernetes": self.parse_kubernetes_files(),
            "environment_vars": self.extract_environment_vars(),
        }
        return self.results

    def parse_dockerfiles(self) -> List[Dict[str, Any]]:
        dockerfiles_data: List[Dict[str, Any]] = []
        dockerfiles = list(self.root_path.rglob("Dockerfile*"))

        for dockerfile in dockerfiles:
            try:
                content = dockerfile.read_text(encoding="utf-8", errors="ignore")

                data = {
                    "path": normalize_path(dockerfile, self.root_path),
                    "base_image": None,
                    "exposed_ports": [],
                    "environment_vars": {},
                    "commands": [],
                }

                from_match = re.search(r"^FROM\s+([^\s]+)", content, re.MULTILINE)
                if from_match:
                    data["base_image"] = from_match.group(1)

                for expose_match in re.finditer(r"^EXPOSE\s+([^\s]+)", content, re.MULTILINE):
                    data["exposed_ports"].append(expose_match.group(1))

                for env_match in re.finditer(r"^ENV\s+(\w+)(?:\s+|=)([^\n]+)", content, re.MULTILINE):
                    data["environment_vars"][env_match.group(1)] = env_match.group(2).strip()

                for cmd_type in ["RUN", "CMD", "ENTRYPOINT"]:
                    pattern = rf"^{cmd_type}\s+(.+)$"
                    for cmd_match in re.finditer(pattern, content, re.MULTILINE):
                        data["commands"].append({
                            "type": cmd_type,
                            "command": cmd_match.group(1).strip(),
                        })

                dockerfiles_data.append(data)
            except Exception:
                continue

        return dockerfiles_data

    def parse_compose_files(self) -> Dict[str, Any]:
        compose_data = {"files": [], "services": []}
        compose_files = list(self.root_path.rglob("docker-compose*.yml")) + \
            list(self.root_path.rglob("docker-compose*.yaml"))

        for compose_file in compose_files:
            if not yaml:
                continue
            try:
                data = yaml.safe_load(compose_file.read_text(encoding="utf-8"))
                if not data or "services" not in data:
                    continue

                compose_data["files"].append(normalize_path(compose_file, self.root_path))

                for service_name, service_config in data.get("services", {}).items():
                    service_info = {
                        "name": service_name,
                        "file": normalize_path(compose_file, self.root_path),
                        "image": service_config.get("image"),
                        "build": service_config.get("build"),
                        "ports": service_config.get("ports", []),
                        "environment": service_config.get("environment", {}),
                        "depends_on": service_config.get("depends_on", []),
                        "volumes": service_config.get("volumes", []),
                        "networks": service_config.get("networks", []),
                    }
                    compose_data["services"].append(service_info)
            except Exception:
                continue

        return compose_data

    def parse_kubernetes_files(self) -> Dict[str, Any]:
        k8s_data = {
            "deployments": [],
            "services": [],
            "ingresses": [],
            "configmaps": [],
        }

        if not yaml:
            return k8s_data

        k8s_dirs = ["k8s", "kubernetes", "deploy", "deployment", ".k8s"]
        k8s_files: List[Path] = []

        for k8s_dir in k8s_dirs:
            k8s_files.extend(self.root_path.rglob(f"{k8s_dir}/*.yaml"))
            k8s_files.extend(self.root_path.rglob(f"{k8s_dir}/*.yml"))

        k8s_files.extend(self.root_path.glob("*.yaml"))
        k8s_files.extend(self.root_path.glob("*.yml"))

        for k8s_file in k8s_files:
            try:
                docs = yaml.safe_load_all(k8s_file.read_text(encoding="utf-8"))
                for doc in docs:
                    if not doc or "kind" not in doc:
                        continue

                    kind = doc.get("kind")
                    metadata = doc.get("metadata", {})
                    spec = doc.get("spec", {})

                    if kind == "Deployment":
                        k8s_data["deployments"].append({
                            "name": metadata.get("name"),
                            "file": normalize_path(k8s_file, self.root_path),
                            "replicas": spec.get("replicas", 1),
                            "containers": [
                                {
                                    "name": c.get("name"),
                                    "image": c.get("image"),
                                    "ports": c.get("ports", []),
                                }
                                for c in spec.get("template", {}).get("spec", {}).get("containers", [])
                            ],
                        })

                    elif kind == "Service":
                        k8s_data["services"].append({
                            "name": metadata.get("name"),
                            "file": normalize_path(k8s_file, self.root_path),
                            "type": spec.get("type"),
                            "ports": spec.get("ports", []),
                            "selector": spec.get("selector", {}),
                        })

                    elif kind == "Ingress":
                        k8s_data["ingresses"].append({
                            "name": metadata.get("name"),
                            "file": normalize_path(k8s_file, self.root_path),
                            "rules": spec.get("rules", []),
                        })

                    elif kind == "ConfigMap":
                        k8s_data["configmaps"].append({
                            "name": metadata.get("name"),
                            "file": normalize_path(k8s_file, self.root_path),
                            "data": doc.get("data", {}),
                        })
            except Exception:
                continue

        return k8s_data

    def extract_environment_vars(self) -> Dict[str, List[Dict[str, Any]]]:
        env_vars: Dict[str, List[Dict[str, Any]]] = {
            "env_files": [],
            "appsettings": [],
        }

        env_files = list(self.root_path.rglob(".env*"))
        for env_file in env_files:
            if env_file.name.endswith(".example") or env_file.name.endswith(".template"):
                continue

            try:
                variables: Dict[str, str] = {}
                for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        variables[key.strip()] = value.strip()

                if variables:
                    env_vars["env_files"].append({
                        "file": normalize_path(env_file, self.root_path),
                        "variables": variables,
                    })
            except Exception:
                continue

        appsettings_files = list(self.root_path.rglob("appsettings*.json"))
        for settings_file in appsettings_files:
            try:
                data = json.loads(settings_file.read_text(encoding="utf-8"))
                env_vars["appsettings"].append({
                    "file": normalize_path(settings_file, self.root_path),
                    "config": data,
                })
            except Exception:
                continue

        return env_vars
