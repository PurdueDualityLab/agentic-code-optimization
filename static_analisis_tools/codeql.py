"""Run CodeQL locally and emit a JSON result plus output.json summary."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

DB_NAME = "codeql-db"
DEFAULT_REPORT_NAME = "output.json"


def _default_output_root() -> Path:
    return Path(__file__).resolve().parent / "output"


def _default_queries_path() -> Path:
    return Path(__file__).resolve().parent / "custom_queries"


def _infer_codeql_root_and_rel(target_path: Path) -> tuple[Path, str]:
    parent = target_path.parent
    if (
        (parent / "deps").exists()
        or (parent / "local_include").exists()
        or (parent / "local_lib").exists()
    ):
        return target_path, "."
    return parent, target_path.name


def _resolve_codeql_context(
    codeql_src: str,
    codeql_rel_path: str,
    codeql_output: str,
    codeql_queries: str,
    target_path: str = "",
) -> dict[str, Any]:
    src_value = codeql_src.strip() if codeql_src else ""
    rel_value = codeql_rel_path.strip() if codeql_rel_path else ""

    if target_path:
        target = Path(target_path).expanduser().resolve()
        if target.exists():
            root, rel_value = _infer_codeql_root_and_rel(target)
            src_value = str(root)

    if not src_value:
        src_value = os.getenv("CODEQL_SRC", "").strip()
    root = Path(src_value) if src_value else Path.cwd()
    root = root.expanduser().resolve()

    if not rel_value:
        rel_value = os.getenv("CODEQL_REL_PATH", ".")
    target = (root / rel_value).resolve()

    output_value = codeql_output.strip() if codeql_output else ""
    if output_value:
        output_base = Path(output_value)
    else:
        default_output = _default_output_root()
        if rel_value and rel_value != ".":
            output_base = default_output / rel_value
        else:
            output_base = default_output / target.name
    output_base = output_base.expanduser().resolve()

    queries_value = codeql_queries.strip() if codeql_queries else ""
    if queries_value:
        queries_path = Path(queries_value).expanduser().resolve()
    else:
        queries_path = _default_queries_path().expanduser().resolve()

    return {
        "root": root,
        "target": target,
        "output_base": output_base,
        "queries_path": queries_path,
        "rel_path": rel_value,
    }


def _run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    ignore_fail: bool = False,
    env: dict[str, str] | None = None,
) -> None:
    print(f"\n$ {' '.join(map(str, cmd))}")
    if cwd:
        print(f"  [in {cwd}]")
    try:
        subprocess.run(list(map(str, cmd)), check=True, cwd=cwd, env=env)
    except subprocess.CalledProcessError as exc:
        if ignore_fail:
            print(f"Command failed (ignored): {exc}")
            return
        raise exc


def _setup_local_dependencies(root: Path) -> None:
    deps_dir = root.parent / "deps"
    deps_dir.mkdir(parents=True, exist_ok=True)

    redis_header = deps_dir / "include/sw/redis++/redis++.h"
    if not redis_header.exists():
        redis_src = root.parent / "redis-plus-plus"
        if redis_src.exists():
            build_dir = redis_src / "build_local"
            build_dir.mkdir(exist_ok=True)
            try:
                _run_cmd(
                    [
                        "cmake",
                        f"-DCMAKE_INSTALL_PREFIX={deps_dir}",
                        "-DCMAKE_BUILD_TYPE=Release",
                        "-DENABLE_STATIC=ON",
                        "-DENABLE_SHARED=OFF",
                        "..",
                    ],
                    cwd=build_dir,
                )
                _run_cmd(["make", "-j4"], cwd=build_dir)
                _run_cmd(["make", "install"], cwd=build_dir)
            except Exception as exc:
                print(f"Failed to build redis-plus-plus: {exc}")

    jwt_header = deps_dir / "include/jwt/jwt.hpp"
    if not jwt_header.exists():
        jwt_src = root.parent / "jwt-cpp"
        if jwt_src.exists():
            build_dir = jwt_src / "build_local"
            build_dir.mkdir(exist_ok=True)
            try:
                _run_cmd(
                    [
                        "cmake",
                        f"-DCMAKE_INSTALL_PREFIX={deps_dir}",
                        "-DCMAKE_BUILD_TYPE=Release",
                        "-DJWT_BUILD_EXAMPLES=OFF",
                        "-DJWT_BUILD_TESTS=OFF",
                        "..",
                    ],
                    cwd=build_dir,
                )
                _run_cmd(["make", "-j4"], cwd=build_dir)
                _run_cmd(["make", "install"], cwd=build_dir)
            except Exception as exc:
                print(f"Failed to build jwt-cpp: {exc}")


def _generate_cpp_build_script(root: Path, cwd: Path) -> str:
    script_path = cwd / "build_codeql.sh"
    build_dir = cwd / "build_codeql"

    _setup_local_dependencies(root)

    deps_dir = root.parent / "deps"
    local_include = root.parent / "local_include"
    local_lib = root.parent / "local_lib"

    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\n")
        handle.write("set -e\n")
        handle.write(f"cd {cwd}\n")

        defines: list[str] = []

        prefixes = [
            str(deps_dir),
            "/opt/homebrew/opt/openssl@3",
            "/opt/homebrew/opt/thrift",
            "/opt/homebrew/opt/mongo-c-driver@1",
            "/opt/homebrew/opt/libevent",
            "/usr/local/opt/openssl@1.1",
            "/usr/local",
        ]
        valid_prefixes = [prefix for prefix in prefixes if os.path.exists(prefix)]
        if valid_prefixes:
            defines.append(f"-DCMAKE_PREFIX_PATH=\"{';'.join(valid_prefixes)}\"")

        cxx_flags: list[str] = []
        if local_include.exists():
            cxx_flags.append(f"-I{local_include}")
            cxx_flags.append(f"-include {local_include}/opentracing/propagation.h")
        if deps_dir.exists():
            cxx_flags.append(f"-I{deps_dir}/include")

        if cxx_flags:
            defines.append(f"-DCMAKE_CXX_FLAGS=\"{' '.join(cxx_flags)}\"")

        defines.append("-DCMAKE_CXX_LINK_EXECUTABLE=\"cmake -E touch <TARGET>\"")

        mongo_cellar = Path("/opt/homebrew/Cellar/mongo-c-driver@1")
        if mongo_cellar.exists():
            versions = sorted(
                [item for item in mongo_cellar.iterdir() if item.is_dir()],
                reverse=True,
            )
            if versions:
                latest_mongo = versions[0]
                mongoc_dir = latest_mongo / "lib/cmake/libmongoc-1.0"
                bson_dir = latest_mongo / "lib/cmake/libbson-1.0"
                if mongoc_dir.exists():
                    defines.append(f"-Dlibmongoc-1.0_DIR=\"{mongoc_dir}\"")
                if bson_dir.exists():
                    defines.append(f"-Dlibbson-1.0_DIR=\"{bson_dir}\"")

        amqp_cellar = Path("/opt/homebrew/Cellar/amqp-cpp")
        if amqp_cellar.exists():
            versions = sorted(
                [item for item in amqp_cellar.iterdir() if item.is_dir()],
                reverse=True,
            )
            if versions:
                latest_amqp = versions[0]
                candidates = [
                    latest_amqp / "lib/cmake/amqpcpp",
                    latest_amqp / "cmake",
                ]
                for path in candidates:
                    if (path / "amqpcppConfig.cmake").exists():
                        defines.append(f"-Damqpcpp_DIR=\"{path}\"")
                        break

        handle.write(
            "export PKG_CONFIG_PATH="
            "\"/opt/homebrew/opt/mongo-c-driver@1/lib/pkgconfig:"
            "/opt/homebrew/lib/pkgconfig:$PKG_CONFIG_PATH\"\n"
        )

        if os.path.exists("/opt/homebrew/opt/thrift"):
            handle.write("export THRIFT_HOME=\"/opt/homebrew/opt/thrift\"\n")

        include_paths: list[str] = []
        if local_include.exists():
            include_paths.append(str(local_include))
        if deps_dir.exists():
            include_paths.append(str(deps_dir / "include"))

        if include_paths:
            path_str = ":" + ":".join(include_paths)
            handle.write(f"export CPATH=\"$CPATH{path_str}\"\n")
            handle.write(f"export C_INCLUDE_PATH=\"$C_INCLUDE_PATH{path_str}\"\n")
            handle.write(f"export CPLUS_INCLUDE_PATH=\"$CPLUS_INCLUDE_PATH{path_str}\"\n")

        if deps_dir.exists():
            handle.write(
                f"export LIBRARY_PATH=\"$LIBRARY_PATH:{deps_dir}/lib:{deps_dir}/lib64\"\n"
            )

        if local_lib.exists():
            handle.write(f"export CODEQL_LOCAL_LIB_DIR=\"{local_lib}\"\n")

        if (cwd / "CMakeLists.txt").exists():
            handle.write(f"BUILD_DIR=\"{build_dir}\"\n")
            handle.write("rm -rf \"$BUILD_DIR\"\n")
            handle.write("mkdir -p \"$BUILD_DIR\"\n")
            cmake_cmd = "cmake -S . -B \"$BUILD_DIR\" " + " ".join(defines)
            handle.write(f"{cmake_cmd}\n")
            handle.write("cmake --build \"$BUILD_DIR\" --parallel 4\n")
        else:
            handle.write("make -j4\n")

    script_path.chmod(0o755)
    return str(script_path)


def _detect_language_and_cmd(root: Path, target: Path) -> tuple[str, str, Path]:
    if (root / "pom.xml").exists():
        return "java", f"mvn clean package -DskipTests -B -f {root}/pom.xml", root

    if (target / "pom.xml").exists():
        return "java", f"mvn clean package -DskipTests -B -f {target}/pom.xml", target

    if (target / "CMakeLists.txt").exists() or (target / "Makefile").exists():
        return "cpp", _generate_cpp_build_script(root, target), target

    if (root / "CMakeLists.txt").exists() or (root / "Makefile").exists():
        return "cpp", _generate_cpp_build_script(root, root), root

    if list(target.glob("**/*.java")) or list(root.glob("**/*.java")):
        return "java", "mvn clean package -DskipTests -B", target

    return "cpp", _generate_cpp_build_script(root, target), target


def _run_summary_script(output_base: Path) -> Path | None:
    summary_script = Path(__file__).resolve().parent / "summarize_sarif.py"
    if not summary_script.exists():
        return None

    env = os.environ.copy()
    env["CODEQL_OUTPUT"] = str(output_base)
    _run_cmd(["python3", str(summary_script)], env=env, ignore_fail=True)
    summary_path = output_base / DEFAULT_REPORT_NAME
    return summary_path if summary_path.exists() else None


def _run_codeql_analysis(
    root: Path,
    target: Path,
    output_base: Path,
    queries_path: Path,
) -> dict[str, Any]:
    codeql_bin = shutil.which("codeql")
    if not codeql_bin:
        return {"error": "codeql_not_found"}

    output_base.mkdir(parents=True, exist_ok=True)

    language, build_cmd, build_cwd = _detect_language_and_cmd(root, target)
    db_path = output_base / DB_NAME
    if db_path.exists():
        shutil.rmtree(db_path, ignore_errors=True)

    notes: list[str] = []

    try:
        _run_cmd(
            [
                codeql_bin,
                "database",
                "create",
                str(db_path),
                f"--language={language}",
                f"--source-root={root}",
                f"--command={build_cmd}",
                "--overwrite",
            ],
            cwd=build_cwd,
        )
    except subprocess.CalledProcessError as exc:
        notes.append(f"database_create_failed: {exc}")
        if not (db_path / "db-java").exists() and not (db_path / "db-cpp").exists():
            return {
                "error": "database_create_failed",
                "root": str(root),
                "target": str(target),
                "output_base": str(output_base),
                "details": notes,
            }

    _run_cmd([codeql_bin, "database", "finalize", str(db_path)], ignore_fail=True)

    sarif_files: list[str] = []
    if language == "cpp":
        suites = ["performance", "component", "behavior"]
        for suite in suites:
            query_dir = queries_path / suite
            if not query_dir.exists():
                notes.append(f"query_suite_missing: {query_dir}")
                continue
            _run_cmd([codeql_bin, "pack", "install", str(query_dir)], ignore_fail=True)
            output_sarif = output_base / f"codeql-{suite}.sarif"
            _run_cmd(
                [
                    codeql_bin,
                    "database",
                    "analyze",
                    str(db_path),
                    str(query_dir),
                    "--format=sarif-latest",
                    "--rerun",
                    "--output",
                    str(output_sarif),
                ],
                ignore_fail=True,
            )
            if output_sarif.exists():
                sarif_files.append(str(output_sarif))
    else:
        _run_cmd(
            [codeql_bin, "pack", "download", "codeql/java-queries"],
            ignore_fail=True,
        )
        output_sarif = output_base / "codeql-java.sarif"
        _run_cmd(
            [
                codeql_bin,
                "database",
                "analyze",
                str(db_path),
                "codeql/java-queries:codeql-suites/java-security-and-quality.qls",
                "--format=sarif-latest",
                "--rerun",
                "--ram=8192",
                "--output",
                str(output_sarif),
            ],
            ignore_fail=True,
        )
        if output_sarif.exists():
            sarif_files.append(str(output_sarif))

    summary_path = _run_summary_script(output_base)

    return {
        "root": str(root),
        "target": str(target),
        "output_base": str(output_base),
        "queries_path": str(queries_path),
        "language": language,
        "build_command": build_cmd,
        "db_path": str(db_path),
        "sarif_files": sarif_files,
        "summary_path": str(summary_path) if summary_path else None,
        "notes": notes,
    }


@tool
def run_codeql_local(
    codeql_src: str = "",
    codeql_rel_path: str = "",
    codeql_output: str = "",
    codeql_queries: str = "",
) -> str:
    """Run CodeQL analysis locally and generate output.json.

    Args:
        codeql_src: Root source directory (CODEQL_SRC). Defaults to env or cwd.
        codeql_rel_path: Relative path within root (CODEQL_REL_PATH).
        codeql_output: Output directory override (defaults to static_analisis_tools/output/<rel_path>).
        codeql_queries: Queries directory override (defaults to static_analisis_tools/custom_queries).

    Returns:
        JSON string with analysis metadata and output paths.
    """
    context = _resolve_codeql_context(
        codeql_src=codeql_src,
        codeql_rel_path=codeql_rel_path,
        codeql_output=codeql_output,
        codeql_queries=codeql_queries,
    )

    root = context["root"]
    target = context["target"]
    output_base = context["output_base"]
    queries_path = context["queries_path"]

    if not root.exists() or not target.exists():
        return json.dumps(
            {
                "error": "path_not_found",
                "root": str(root),
                "target": str(target),
            },
            indent=2,
        )

    payload = _run_codeql_analysis(root, target, output_base, queries_path)
    return json.dumps(payload, indent=2)


def run_codeql_direct(
    target_path: str,
    codeql_output: str = "",
    codeql_queries: str = "",
) -> str:
    context = _resolve_codeql_context(
        codeql_src="",
        codeql_rel_path="",
        codeql_output=codeql_output,
        codeql_queries=codeql_queries,
        target_path=target_path,
    )
    payload = _run_codeql_analysis(
        context["root"],
        context["target"],
        context["output_base"],
        context["queries_path"],
    )
    return json.dumps(payload, indent=2)


def _parse_args() -> dict[str, str]:
    parser = argparse.ArgumentParser(
        description="Run CodeQL locally and emit JSON output."
    )
    parser.add_argument("target_path", help="Target repository path to analyze")
    parser.add_argument(
        "--output",
        default="",
        help="Output directory override (default: static_analisis_tools/output/<target>)",
    )
    parser.add_argument(
        "--queries",
        default="",
        help="Queries directory override (default: static_analisis_tools/custom_queries)",
    )
    args = parser.parse_args()
    return {"target_path": args.target_path, "output": args.output, "queries": args.queries}


def main() -> None:
    args = _parse_args()
    result = run_codeql_direct(
        args["target_path"],
        codeql_output=args["output"],
        codeql_queries=args["queries"],
    )
    print(result)


if __name__ == "__main__":
    main()
