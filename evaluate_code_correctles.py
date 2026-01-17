"""Evaluation script for optimization workflow plus code correctness check."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from beautilog import logger
from dotenv import load_dotenv

from config import ConfigParser, WorkflowConfig
from utils import RunManager
from workflows.optimization_correctness_orchestrator import (
    orchestrate_optimization_correctness,
)

load_dotenv()

SPEC_ENV_VAR = "CODE_CORRECTNESS_SPEC"
BENCHMARK_CMD_ENV_VAR = "BENCHMARK_CMD"
BENCHMARK_TIMEOUT_ENV_VAR = "BENCHMARK_TIMEOUT"


def _load_spec(spec: str, spec_file: str) -> str:
    if spec:
        return spec
    if spec_file:
        return Path(spec_file).read_text(encoding="utf-8", errors="ignore")
    env_spec = os.getenv(SPEC_ENV_VAR, "")
    return env_spec


def _load_benchmark_cmd(cmd: str) -> str:
    if cmd:
        return cmd
    return os.getenv(BENCHMARK_CMD_ENV_VAR, "")


def _load_benchmark_timeout(value: str) -> int | None:
    if value:
        try:
            return int(value)
        except ValueError:
            return None
    env_value = os.getenv(BENCHMARK_TIMEOUT_ENV_VAR, "")
    if not env_value:
        return None
    try:
        return int(env_value)
    except ValueError:
        return None


def _load_benchmark_enabled() -> bool:
    try:
        return bool(ConfigParser.get(WorkflowConfig).enable_benchmark)
    except Exception:
        return True


def evaluate_code_correctness_workflow(
    repo_path: str,
    spec: str,
    analysis_source: str,
    benchmark_cmd: str,
    benchmark_timeout: int | None,
    benchmark_enabled: bool,
    mode: str,
    language: str,
    change_index: int | None,
    use_diff: bool,
) -> None:
    repo_path_obj = Path(repo_path)

    if not repo_path_obj.exists():
        print(f"ERROR: Repository path does not exist: {repo_path}")
        sys.exit(1)

    run_manager = RunManager()
    run_dir = run_manager.create_run_dir(repo_path, "OptimizationBenchmarkCorrectnessWorkflow")
    print(f"\nRun directory created: {run_dir}")

    run_manager.save_config(Path.cwd() / "config.ini")
    run_manager.save_input(repo_path, "OptimizationBenchmarkCorrectnessWorkflow")
    logger.update_log_file_path(run_dir / "execution.log")

    print("=" * 80)
    print("BENCHMARK + SUMMARY + STATIC ANALYSIS + ANALYSIS + OPTIMIZATION + CODE CORRECTNESS + BENCHMARK")
    print("=" * 80)
    print()

    print("TARGET:")
    print(f"  Repository Path: {repo_path_obj.absolute()}")
    print(f"  Path Exists: {repo_path_obj.exists()}")
    print(f"  Is Directory: {repo_path_obj.is_dir()}")
    print(f"  Analysis Source: {analysis_source or '(auto)'}")
    print(f"  Benchmark Enabled: {benchmark_enabled}")
    print(f"  Run Directory: {run_dir}")
    print()

    if benchmark_enabled and not benchmark_cmd:
        print("ERROR: Missing benchmark command.")
        print(f"Set {BENCHMARK_CMD_ENV_VAR} in .env or pass --benchmark-cmd.")
        sys.exit(1)

    print("RUNNING WORKFLOW...")
    print("-" * 80)

    try:
        logger.info(f"Starting full workflow for repository: {repo_path_obj.absolute()}")
        start_time = time.time()
        result = orchestrate_optimization_correctness(
            code_path=str(repo_path_obj.absolute()),
            analysis_source=analysis_source,
            benchmark_cmd=benchmark_cmd,
            benchmark_timeout=benchmark_timeout,
            benchmark_artifact_dir=str(run_dir),
            benchmark_enabled=benchmark_enabled,
            spec=spec,
            mode=mode,
            language=language,
            change_index=change_index,
            use_diff=use_diff,
        )
        execution_time = time.time() - start_time
        logger.info(f"Full workflow completed in {execution_time:.2f}s")

        optimization_report = result.get("optimization_report", "")
        correctness_report = result.get("correctness_report", "")
        benchmark_report = result.get("benchmark_report", "")
        print("\nOPTIMIZATION REPORT:")
        print(optimization_report[:2000] + "..." if len(optimization_report) > 2000 else optimization_report)
        print("\nCORRECTNESS REPORT:")
        print(correctness_report[:2000] + "..." if len(correctness_report) > 2000 else correctness_report)
        print("\nBENCHMARK REPORT:")
        print(benchmark_report[:2000] + "..." if len(benchmark_report) > 2000 else benchmark_report)

    except Exception as exc:
        logger.error(f"Workflow execution failed: {str(exc)}", exc_info=True)
        print(f"ERROR: Workflow execution failed: {str(exc)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("-" * 80)

    combined = {
        "optimization_report": optimization_report,
        "correctness_report": correctness_report,
        "benchmark_report": benchmark_report,
    }

    output_text = json.dumps(combined, indent=2)
    run_manager.save_response(output_text)
    response_json = run_dir / "response.json"
    response_json.write_text(output_text, encoding="utf-8")

    metrics = {
        "workflow": "OptimizationBenchmarkCorrectnessWorkflow",
        "execution_time_seconds": round(execution_time, 2),
        "result_length": len(output_text),
    }
    run_manager.save_metrics(metrics)

    print(f"All results saved to: {run_dir}")
    run_info = run_manager.get_run_info()
    print(f"   Artifacts: {', '.join(run_info['artifacts'])}")
    print()

    print("=" * 80)
    print("EVALUATION COMPLETE")
    print("=" * 80)
    logger.info("Optimization benchmark correctness workflow evaluation completed successfully")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run optimization workflow and code correctness check",
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=str(Path(__file__).parent.absolute()),
        help="Path to repository",
    )
    parser.add_argument("--analysis-source", default="", help="Path to analysis JSON")
    parser.add_argument("--benchmark-cmd", default="", help="Benchmark command to run")
    parser.add_argument("--benchmark-timeout", default="", help="Benchmark timeout in seconds")
    parser.add_argument("--spec", default="", help="Problem statement spec (optional)")
    parser.add_argument("--spec-file", default="", help="Path to problem statement text (optional)")
    parser.add_argument(
        "--mode",
        default="analyze_then_summarize",
        choices=["analyze_then_summarize", "fault_localization"],
        help="Correctness check mode",
    )
    parser.add_argument("--language", default="C++", help="Language label for prompt")
    parser.add_argument(
        "--change-index",
        type=int,
        default=None,
        help="Index of applied change to check (default: all)",
    )
    parser.add_argument(
        "--use-diff",
        action="store_true",
        help="Use diff snippet instead of full file",
    )
    args = parser.parse_args()

    spec = _load_spec(args.spec, args.spec_file)
    benchmark_cmd = _load_benchmark_cmd(args.benchmark_cmd)
    benchmark_timeout = _load_benchmark_timeout(args.benchmark_timeout)
    benchmark_enabled = _load_benchmark_enabled()
    evaluate_code_correctness_workflow(
        repo_path=args.repo_path,
        spec=spec,
        analysis_source=args.analysis_source,
        benchmark_cmd=benchmark_cmd,
        benchmark_timeout=benchmark_timeout,
        benchmark_enabled=benchmark_enabled,
        mode=args.mode,
        language=args.language,
        change_index=args.change_index,
        use_diff=args.use_diff,
    )


if __name__ == "__main__":
    main()
