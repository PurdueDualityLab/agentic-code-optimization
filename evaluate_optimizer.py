"""Evaluation script for optimization workflow using LangGraph orchestrator."""

import json
import sys
import time
from pathlib import Path

from beautilog import logger
from dotenv import load_dotenv

from utils import RunManager
from workflows.optimization_orchestrator import orchestrate_optimization

load_dotenv()


def evaluate_optimization_workflow(repo_path: str, analysis_source: str = "") -> None:
    """Evaluate the optimization workflow on a given repository."""
    repo_path_obj = Path(repo_path)

    if not repo_path_obj.exists():
        print(f"ERROR: Repository path does not exist: {repo_path}")
        sys.exit(1)

    run_manager = RunManager()
    run_dir = run_manager.create_run_dir(repo_path, "OptimizationWorkflow")
    print(f"\nRun directory created: {run_dir}")

    run_manager.save_config(Path.cwd() / "config.ini")
    run_manager.save_input(repo_path, "OptimizationWorkflow")
    logger.update_log_file_path(run_dir / "execution.log")

    print("=" * 80)
    print("OPTIMIZATION WORKFLOW EVALUATION")
    print("=" * 80)
    print()

    print("OPTIMIZATION TARGET:")
    print(f"  Repository Path: {repo_path_obj.absolute()}")
    print(f"  Path Exists: {repo_path_obj.exists()}")
    print(f"  Is Directory: {repo_path_obj.is_dir()}")
    print(f"  Analysis Source: {analysis_source or '(auto)'}")
    print(f"  Run Directory: {run_dir}")
    print()

    print("RUNNING WORKFLOW...")
    print("-" * 80)

    try:
        logger.info(f"Starting optimization workflow for repository: {repo_path_obj.absolute()}")
        start_time = time.time()
        result = orchestrate_optimization(str(repo_path_obj.absolute()), analysis_source)
        execution_time = time.time() - start_time
        logger.info(f"Optimization workflow completed successfully in {execution_time:.2f}s")

        optimization_report = result.get("optimization_report", "")
        print("\nOPTIMIZATION REPORT:")
        print(optimization_report[:2000] + "..." if len(optimization_report) > 2000 else optimization_report)

    except Exception as e:
        logger.error(f"Workflow execution failed: {str(e)}", exc_info=True)
        print(f"ERROR: Workflow execution failed: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("-" * 80)

    print("EXECUTION SUMMARY:")
    print(f"  Execution Time: {execution_time:.2f} seconds")
    print(f"  Result Length: {len(optimization_report)}")
    print()

    run_manager.save_response(optimization_report)
    try:
        parsed = json.loads(optimization_report)
    except Exception:
        parsed = None
    if parsed is not None:
        response_json = run_dir / "response.json"
        with open(response_json, "w") as f:
            json.dump(parsed, f, indent=2)

    metrics = {
        "workflow": "OptimizationWorkflow",
        "execution_time_seconds": execution_time,
        "result_length": len(optimization_report),
    }
    run_manager.save_metrics(metrics)

    print(f"All results saved to: {run_dir}")
    run_info = run_manager.get_run_info()
    print(f"   Artifacts: {', '.join(run_info['artifacts'])}")
    print()

    print("=" * 80)
    print("EVALUATION COMPLETE")
    print("=" * 80)
    logger.info("Optimization workflow evaluation completed successfully")


def main() -> None:
    """Main entry point."""
    repo_path = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent.absolute())
    analysis_source = sys.argv[2] if len(sys.argv) > 2 else ""
    evaluate_optimization_workflow(repo_path, analysis_source)


if __name__ == "__main__":
    main()
