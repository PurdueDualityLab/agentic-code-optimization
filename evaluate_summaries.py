"""Evaluation script for summarization workflow using LangGraph orchestrator.

This script runs the complete summarization workflow (Environment, Component, Behavior)
using the LangGraph-based orchestrator with RunManager for artifact management.

Usage:
    python evaluate_summaries.py                  # Run on current project
    python evaluate_summaries.py <repo_path>      # Run on specific repository
"""

import sys
import time
from pathlib import Path

from beautilog import logger
from dotenv import load_dotenv

from utils import RunManager
from workflows.summary_orchestrator import orchestrate_summarizers

load_dotenv()


def evaluate_summarization_workflow(repo_path: str) -> None:
    """Evaluate the summarization workflow on a given repository.

    Args:
        repo_path: Path to the repository to analyze
    """
    repo_path_obj = Path(repo_path)

    if not repo_path_obj.exists():
        print(f"❌ Error: Repository path does not exist: {repo_path}")
        sys.exit(1)

    # Create run manager and directory
    run_manager = RunManager()
    run_dir = run_manager.create_run_dir(repo_path, "SummarizationWorkflow")
    print(f"\n📁 Run directory created: {run_dir}")

    # Setup run environment
    run_manager.save_config(Path.cwd() / "config.ini")
    run_manager.save_input(repo_path, "SummarizationWorkflow")
    logger.update_log_file_path(run_dir / "execution.log")

    print("=" * 80)
    print("SUMMARIZATION WORKFLOW EVALUATION")
    print("=" * 80)
    print()

    # Display analysis target
    print("ANALYSIS TARGET:")
    print(f"  Repository Path: {repo_path_obj.absolute()}")
    print(f"  Path Exists: {repo_path_obj.exists()}")
    print(f"  Is Directory: {repo_path_obj.is_dir()}")
    print(f"  Run Directory: {run_dir}")
    print()

    # Run the workflow
    print("RUNNING WORKFLOW...")
    print("-" * 80)

    try:
        logger.info(f"Starting summarization workflow for repository: {repo_path_obj.absolute()}")
        start_time = time.time()
        result = orchestrate_summarizers(str(repo_path_obj.absolute()))
        execution_time = time.time() - start_time
        logger.info(f"Summarization workflow completed successfully in {execution_time:.2f}s")

        # Display results
        print("\nWORKFLOW RESULTS:")
        print()
        if "environment_summary" in result and result["environment_summary"]:
            print("ENVIRONMENT SUMMARY:")
            print(result["environment_summary"][:500] + "..." if len(str(result["environment_summary"])) > 500 else result["environment_summary"])
            print()

        if "component_summary" in result and result["component_summary"]:
            print("COMPONENT SUMMARY:")
            print(result["component_summary"][:500] + "..." if len(str(result["component_summary"])) > 500 else result["component_summary"])
            print()

        if "behavior_summary" in result and result["behavior_summary"]:
            print("BEHAVIOR SUMMARY:")
            print(result["behavior_summary"][:500] + "..." if len(str(result["behavior_summary"])) > 500 else result["behavior_summary"])
            print()

    except Exception as e:
        logger.error(f"Workflow execution failed: {str(e)}", exc_info=True)
        print(f"❌ Workflow execution failed: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("-" * 80)

    # Execution summary
    print("EXECUTION SUMMARY:")
    print(f"  Execution Time: {execution_time:.2f} seconds")
    print(f"  Total Results: {len(result)}")
    print()

    # Save execution results to run directory
    result_summary = {
        "environment_summary": result.get("environment_summary", "")[:200] + "...",
        "component_summary": result.get("component_summary", "")[:200] + "...",
        "behavior_summary": result.get("behavior_summary", "")[:200] + "...",
    }
    run_manager.save_response(str(result_summary))

    metrics = {
        "workflow": "SummarizationWorkflow",
        "execution_time_seconds": execution_time,
        "total_agents_run": 3,
        "results_generated": len(result),
        "environment_summary_length": len(str(result.get("environment_summary", ""))),
        "component_summary_length": len(str(result.get("component_summary", ""))),
        "behavior_summary_length": len(str(result.get("behavior_summary", ""))),
    }
    run_manager.save_metrics(metrics)

    print(f"✅ All results saved to: {run_dir}")
    run_info = run_manager.get_run_info()
    print(f"   Artifacts: {', '.join(run_info['artifacts'])}")
    print()

    print("=" * 80)
    print("✓ EVALUATION COMPLETE")
    print("=" * 80)
    logger.info("Summarization workflow evaluation completed successfully")


def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1:
        repo_path = sys.argv[1]
    else:
        # Use current project directory as default
        repo_path = str(Path(__file__).parent.absolute())

    evaluate_summarization_workflow(repo_path)


if __name__ == "__main__":
    main()
