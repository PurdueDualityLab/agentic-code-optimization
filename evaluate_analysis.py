"""Evaluation script for analysis workflow using LangGraph orchestrator."""

import json
import sys
import time
from pathlib import Path

from beautilog import logger
from dotenv import load_dotenv

from utils import RunManager
from workflows.analysis_orchestrator import orchestrate_analysis

load_dotenv()


def evaluate_analysis_workflow(repo_path: str) -> None:
    """Evaluate the analysis workflow on a given repository."""
    repo_path_obj = Path(repo_path)

    if not repo_path_obj.exists():
        print(f"ERROR: Repository path does not exist: {repo_path}")
        sys.exit(1)

    run_manager = RunManager()
    run_dir = run_manager.create_run_dir(repo_path, "AnalysisWorkflow")
    print(f"\nRun directory created: {run_dir}")

    run_manager.save_config(Path.cwd() / "config.ini")
    run_manager.save_input(repo_path, "AnalysisWorkflow")
    logger.update_log_file_path(run_dir / "execution.log")

    print("=" * 80)
    print("ANALYSIS WORKFLOW EVALUATION")
    print("=" * 80)
    print()

    print("ANALYSIS TARGET:")
    print(f"  Repository Path: {repo_path_obj.absolute()}")
    print(f"  Path Exists: {repo_path_obj.exists()}")
    print(f"  Is Directory: {repo_path_obj.is_dir()}")
    print(f"  Run Directory: {run_dir}")
    print()

    print("RUNNING WORKFLOW...")
    print("-" * 80)

    try:
        logger.info(f"Starting analysis workflow for repository: {repo_path_obj.absolute()}")
        start_time = time.time()
        result = orchestrate_analysis(str(repo_path_obj.absolute()))
        execution_time = time.time() - start_time
        logger.info(f"Analysis workflow completed successfully in {execution_time:.2f}s")

        analysis_report = result.get("analysis_report", "")
        print("\nANALYSIS REPORT:")
        print(analysis_report[:2000] + "..." if len(analysis_report) > 2000 else analysis_report)

    except Exception as e:
        logger.error(f"Workflow execution failed: {str(e)}", exc_info=True)
        print(f"ERROR: Workflow execution failed: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("-" * 80)

    print("EXECUTION SUMMARY:")
    print(f"  Execution Time: {execution_time:.2f} seconds")
    print(f"  Result Length: {len(analysis_report)}")
    print()

    run_manager.save_response(analysis_report)
    try:
        parsed = json.loads(analysis_report)
    except Exception:
        parsed = None
    if parsed is not None:
        response_json = run_dir / "response.json"
        with open(response_json, "w") as f:
            json.dump(parsed, f, indent=2)
    metrics = {
        "workflow": "AnalysisWorkflow",
        "execution_time_seconds": execution_time,
        "result_length": len(analysis_report),
    }
    run_manager.save_metrics(metrics)

    print(f"All results saved to: {run_dir}")
    run_info = run_manager.get_run_info()
    print(f"   Artifacts: {', '.join(run_info['artifacts'])}")
    print()

    print("=" * 80)
    print("EVALUATION COMPLETE")
    print("=" * 80)
    logger.info("Analysis workflow evaluation completed successfully")


def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1:
        repo_path = sys.argv[1]
    else:
        repo_path = str(Path(__file__).parent.absolute())

    evaluate_analysis_workflow(repo_path)


if __name__ == "__main__":
    main()
