"""Evaluation script for the complete optimization pipeline.

This script runs the complete three-phase optimization pipeline:
1. Summarization (environment, component, behavior summaries)
2. Analysis (structured optimization guidance)
3. Optimization (apply safe code improvements)

Usage:
    python evaluate_complete_pipeline.py                  # Run on current project
    python evaluate_complete_pipeline.py <repo_path>      # Run on specific repository
"""

import json
import logging
import sys
import time
from pathlib import Path

from beautilog import logger
from dotenv import load_dotenv

from utils import RunManager
from workflows.complete_pipeline import MAX_ITERATIONS, orchestrate_complete_pipeline

load_dotenv()


def evaluate_complete_pipeline(repo_path: str) -> None:
    """Evaluate the complete optimization pipeline on a given repository.

    Args:
        repo_path: Path to the repository to analyze and optimize
    """
    repo_path_obj = Path(repo_path)

    if not repo_path_obj.exists():
        print(f"❌ Error: Repository path does not exist: {repo_path}")
        sys.exit(1)

    # Create run manager and directory
    run_manager = RunManager()
    run_dir = run_manager.create_run_dir(repo_path, "CompletePipeline")
    print(f"\n📁 Run directory created: {run_dir}")

    # Setup run environment
    run_manager.save_config(Path.cwd() / "config.ini")
    run_manager.save_input(repo_path, "CompletePipeline")
    logger.update_log_file_path(run_dir / "execution.log")

    print("=" * 80)
    print("COMPLETE OPTIMIZATION PIPELINE EVALUATION")
    print("=" * 80)
    print()

    # Display pipeline configuration
    print("PIPELINE CONFIGURATION:")
    print("  Name: Complete Optimization Pipeline")
    print("  Phases: 3 (Summarization, Analysis, Optimization)")
    print("  Nodes: 4 (summarization, static_analysis, analysis, optimization)")
    print()

    # Display analysis target
    print("ANALYSIS TARGET:")
    print(f"  Repository Path: {repo_path_obj.absolute()}")
    print(f"  Path Exists: {repo_path_obj.exists()}")
    print(f"  Is Directory: {repo_path_obj.is_dir()}")
    print(f"  Run Directory: {run_dir}")
    print()

    # Run the complete pipeline
    print("RUNNING PIPELINE...")
    print("-" * 80)

    try:
        logger.info(
            f"Starting complete optimization pipeline for repository: {repo_path_obj.absolute()}"
        )
        start_time = time.time()

        # Execute the complete pipeline
        final_state = orchestrate_complete_pipeline(str(repo_path_obj.absolute()))

        execution_time = time.time() - start_time
        logger.info(
            f"Pipeline execution completed successfully in {execution_time:.2f} seconds"
        )

        # Extract results from final state
        optimization_report = final_state.get("optimization_report", "")
        analysis_report = final_state.get("analysis_report", "")
        correctness_report = final_state.get("correctness_report", "")
        summary_text = final_state.get("summary_text", "")
        iteration_count = final_state.get("iteration_count", 0)

        print("Pipeline execution completed!")
        print()

    except Exception as e:
        logger.error(f"Pipeline execution failed: {str(e)}", exc_info=True)
        print(f"❌ Pipeline execution failed: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("-" * 80)

    # Execution summary
    print("EXECUTION SUMMARY:")
    print(f"  Execution Time: {execution_time:.2f} seconds")
    print(f"  Iterations Completed: {iteration_count}/{MAX_ITERATIONS}")
    print(f"  Summary Text Length: {len(summary_text)} characters")
    print(f"  Analysis Report Length: {len(analysis_report)} characters")
    print(f"  Optimization Report Length: {len(optimization_report)} characters")
    print(f"  Correctness Report Length: {len(correctness_report)} characters")
    print()

    # Parse and display analysis report if available
    print("ANALYSIS RESULTS:")
    try:
        if analysis_report:
            analysis_json = json.loads(analysis_report)
            priorities = analysis_json.get("priorities", [])
            risks = analysis_json.get("risks_and_gaps", [])
            focus_files = analysis_json.get("suggested_focus_files", [])

            print(f"  Priorities Identified: {len(priorities)}")
            for i, priority in enumerate(priorities[:5], 1):
                title = priority.get("title", "Unknown")
                confidence = priority.get("confidence", "Unknown")
                print(f"    {i}. {title} [{confidence}]")
            if len(priorities) > 5:
                print(f"    ... and {len(priorities) - 5} more")

            print(f"  Risks/Gaps: {len(risks)}")
            print(f"  Focus Files: {len(focus_files)}")
            print()
    except (json.JSONDecodeError, KeyError):
        print("  (Could not parse analysis report)")
        print()

    # Parse and display optimization report if available
    print("OPTIMIZATION RESULTS:")
    try:
        if optimization_report:
            optimization_json = json.loads(optimization_report)
            applied_changes = optimization_json.get("applied_changes", [])
            skipped_priorities = optimization_json.get("skipped_priorities", [])
            risks = optimization_json.get("risks", [])

            print(f"  Applied Changes: {len(applied_changes)}")
            for i, change in enumerate(applied_changes[:5], 1):
                file_path = change.get("file", "Unknown")
                summary = change.get("summary", "Unknown")
                print(f"    {i}. {file_path}: {summary}")
            if len(applied_changes) > 5:
                print(f"    ... and {len(applied_changes) - 5} more")

            print(f"  Skipped Priorities: {len(skipped_priorities)}")
            print(f"  Risks: {len(risks)}")
            print()
    except (json.JSONDecodeError, KeyError):
        print("  (Could not parse optimization report)")
        print()

    # Parse and display correctness check report if available
    print("CORRECTNESS CHECK RESULTS:")
    try:
        if correctness_report:
            print(f"  Report Length: {len(correctness_report)} characters")
            print(f"  Report Preview: {correctness_report[:200]}...")
            print()
    except Exception:
        print("  (Could not parse correctness report)")
        print()

    # Save execution results to run directory
    run_manager.save_response(
        json.dumps(
            {
                "optimization_report": optimization_report,
                "analysis_report": analysis_report,
                "correctness_report": correctness_report,
                "summary_text": summary_text,
                "iteration_count": iteration_count,
            },
            indent=2,
        )
    )

    metrics = {
        "execution_time_seconds": execution_time,
        "iterations_completed": iteration_count,
        "max_iterations": MAX_ITERATIONS,
        "summary_length": len(summary_text),
        "analysis_length": len(analysis_report),
        "optimization_length": len(optimization_report),
        "correctness_length": len(correctness_report),
    }

    # Add analysis metrics if available
    try:
        if analysis_report:
            analysis_json = json.loads(analysis_report)
            metrics["priorities_count"] = len(analysis_json.get("priorities", []))
            metrics["risks_count"] = len(analysis_json.get("risks_and_gaps", []))
            metrics["focus_files_count"] = len(analysis_json.get("suggested_focus_files", []))
    except (json.JSONDecodeError, KeyError):
        pass

    # Add optimization metrics if available
    try:
        if optimization_report:
            optimization_json = json.loads(optimization_report)
            metrics["applied_changes_count"] = len(optimization_json.get("applied_changes", []))
            metrics["skipped_priorities_count"] = len(
                optimization_json.get("skipped_priorities", [])
            )
            metrics["risks_count"] = len(optimization_json.get("risks", []))
    except (json.JSONDecodeError, KeyError):
        pass

    run_manager.save_metrics(metrics)
    run_manager.save_summary(
        None,
        json.dumps(
            {
                "optimization_report": optimization_report,
                "analysis_report": analysis_report,
                "correctness_report": correctness_report,
                "iteration_count": iteration_count,
            },
            indent=2,
        ),
        execution_time,
        custom_title="Complete Optimization Pipeline Results",
    )

    print(f"✅ All results saved to: {run_dir}")
    run_info = run_manager.get_run_info()
    print(f"   Artifacts: {', '.join(run_info['artifacts'])}")
    print()

    print("=" * 80)
    print("✓ PIPELINE EVALUATION COMPLETE")
    print("=" * 80)
    logger.info("Pipeline evaluation completed successfully")


def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1:
        repo_path = sys.argv[1]
    else:
        # Use current project directory as default
        repo_path = str(Path(__file__).parent.absolute())

    evaluate_complete_pipeline(repo_path)


if __name__ == "__main__":
    main()
