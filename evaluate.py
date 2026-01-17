"""Evaluation script for agents with simplified structure.

This script demonstrates how to run agents with the new simplified BaseAgent.

Usage:
    python evaluate.py                          # Run on current project
    python evaluate.py <repo_path>              # Run on specific repository
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

from beautilog import logger
from dotenv import load_dotenv

from agents.summarizers import EnvironmentSummarizer
from utils import RunManager

load_dotenv()


async def evaluate_environment_summarizer(repo_path: str) -> None:
    """Evaluate EnvironmentSummarizer on a given repository.

    Args:
        repo_path: Path to the repository to analyze
    """
    repo_path_obj = Path(repo_path)

    if not repo_path_obj.exists():
        print(f"❌ Error: Repository path does not exist: {repo_path}")
        sys.exit(1)

    # Create agent
    agent = EnvironmentSummarizer()

    # Create run manager and directory
    run_manager = RunManager()
    run_dir = run_manager.create_run_dir(repo_path, agent.name)
    print(f"\n📁 Run directory created: {run_dir}")

    # Setup run environment
    run_manager.save_config(Path.cwd() / "config.ini")
    run_manager.save_input(repo_path, agent.name)
    logger.update_log_file_path(run_dir / "execution.log")

    print("=" * 80)
    print("ENVIRONMENT SUMMARIZER EVALUATION")
    print("=" * 80)
    print()

    # Display agent configuration
    print("AGENT CONFIGURATION:")
    print(f"  Name: {agent.name}")
    print(f"  Provider: {agent.llm.__class__.__name__}")
    print(f"  Temperature: {agent.temperature}")
    print(f"  Max Iterations: {agent.max_iterations}")
    print(f"  Tools: {len(agent.tools)}")
    print(f"  Return State Field: {agent.return_state_field}")
    print()

    # Display analysis target
    print("ANALYSIS TARGET:")
    print(f"  Repository Path: {repo_path_obj.absolute()}")
    print(f"  Path Exists: {repo_path_obj.exists()}")
    print(f"  Is Directory: {repo_path_obj.is_dir()}")
    print(f"  Run Directory: {run_dir}")
    print()

    # Run the agent
    print("RUNNING AGENT...")
    print("-" * 80)

    try:
        logger.info(f"Starting agent execution for repository: {repo_path_obj.absolute()}")
        start_time = time.time()
        result = await agent.run(str(repo_path_obj.absolute()))
        execution_time = time.time() - start_time
        logger.info(f"Agent execution completed successfully, result length: {len(result) if result else 0}")
        print(result)
    except Exception as e:
        logger.error(f"Agent execution failed: {str(e)}", exc_info=True)
        print(f"❌ Agent execution failed: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print()
    print("-" * 80)

    # Execution summary
    print("EXECUTION SUMMARY:")
    print(f"  Iterations: {agent.iteration_count}/{agent.max_iterations}")
    print(f"  Tools Used: {agent.tools_used_count}")
    print(f"  Unique Tools Used: {len(agent.tools_used_names)}")
    print(f"  Tools Used Names: {agent.tools_used_names}")
    print(f"  Final Result Length: {len(result) if result else 0} characters")
    print(f"  Execution Time: {execution_time:.2f} seconds")
    print()

    # Display LangGraph output format
    print("LANGGRAPH OUTPUT FORMAT:")
    langgraph_output = agent.get_langgraph_output()
    print(f"  Fields: {list(langgraph_output.keys())}")
    print(f"  Result Key: {agent.return_state_field}")
    print()

    # Save execution results to run directory
    run_manager.save_response(result)
    metrics = {
        "llm_iterations": agent.iteration_count,
        "tools_used_total": agent.tools_used_count,
        "unique_tools_used": len(agent.tools_used_names),
        "tools_list": agent.tools_used_names,
        "result_length": len(result) if result else 0,
        "execution_time_seconds": execution_time,
        "max_iterations": agent.max_iterations,
        "temperature": agent.temperature,
        "provider": agent.llm.__class__.__name__,
    }
    run_manager.save_metrics(metrics)
    run_manager.save_state(agent)
    run_manager.save_summary(agent, result, execution_time)

    print(f"✅ All results saved to: {run_dir}")
    run_info = run_manager.get_run_info()
    print(f"   Artifacts: {', '.join(run_info['artifacts'])}")
    print()

    print("=" * 80)
    print("✓ EVALUATION COMPLETE")
    print("=" * 80)
    logger.info("Evaluation completed successfully")


def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1:
        repo_path = sys.argv[1]
    else:
        # Use current project directory as default
        repo_path = str(Path(__file__).parent.absolute())

    asyncio.run(evaluate_environment_summarizer(repo_path))


if __name__ == "__main__":
    main()
