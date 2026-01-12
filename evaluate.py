"""Evaluation script for agents with simplified structure.

This script demonstrates how to run agents with the new simplified BaseAgent.

Usage:
    python evaluate.py                          # Run on current project
    python evaluate.py <repo_path>              # Run on specific repository
"""

import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

from beautilog import logger
from dotenv import load_dotenv

from agents.summarizers import EnvironmentSummarizer

load_dotenv()


def create_run_directory(repo_path: str, agent_name: str) -> Path:
    """Create a new run directory with timestamp.

    Args:
        repo_path: Path to the repository being analyzed
        agent_name: Name of the agent being used
    Returns:
        Path to the created run directory
    """
    repo_name = Path(repo_path).name or "project"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path.cwd() / "runs" / f"{agent_name}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def setup_run_environment(run_dir: Path, repo_path: str, agent_name: str) -> None:
    """Setup run environment by copying config and saving input parameters.

    Args:
        run_dir: Path to the run directory
        repo_path: Path to the repository being analyzed
        agent_name: Name of the agent being used
    """
    # Copy config.ini
    config_file = Path.cwd() / "config.ini"
    if config_file.exists():
        shutil.copy(config_file, run_dir / "config.ini")
        logger.info(f"Copied config.ini to run directory")
    else:
        logger.warning("config.ini not found in current directory")

    # Save input parameters
    input_data = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name,
        "repository_path": str(Path(repo_path).absolute()),
        "repository_name": Path(repo_path).name or "project",
        "working_directory": str(Path.cwd()),
    }
    input_file = run_dir / "input.txt"
    with open(input_file, "w") as f:
        for key, value in input_data.items():
            f.write(f"{key}: {value}\n")
    logger.info(f"Saved input parameters to input.txt")


def save_execution_results(
    run_dir: Path, agent, result: str, execution_time: float
) -> None:
    """Save execution results to run directory.

    Args:
        run_dir: Path to the run directory
        agent: The executed agent instance
        result: The result from agent execution
        execution_time: Time taken for execution in seconds
    """
    # Save response
    response_file = run_dir / "response.txt"
    with open(response_file, "w") as f:
        f.write(result if result else "")
    logger.info(f"Saved response to response.txt")

    # Save metrics
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
    metrics_file = run_dir / "metrics.json"
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Saved metrics to metrics.json")

    # Save agent state
    langgraph_output = agent.get_langgraph_output()
    state_data = {
        "return_state_field": agent.return_state_field,
        "output": langgraph_output,
        "message_count": len(agent.messages),
        "messages": agent.messages,
        "tools_used_names": agent.tools_used_names,
    }
    state_file = run_dir / "state.json"
    with open(state_file, "w") as f:
        json.dump(state_data, f, indent=2, default=str)
    logger.info(f"Saved state to state.json")

    # Save execution summary
    summary_file = run_dir / "summary.md"
    with open(summary_file, "w") as f:
        f.write("# Execution Summary\n\n")
        f.write(f"**Timestamp:** {datetime.now().isoformat()}\n\n")
        f.write(f"**Agent:** {agent.name}\n\n")
        f.write(f"## Metrics\n\n")
        for key, value in metrics.items():
            f.write(f"- **{key}:** {value}\n")
        f.write(f"\n## Results\n\n")
        f.write(f"Result length: {len(result) if result else 0} characters\n")
    logger.info(f"Saved summary to summary.md")


def evaluate_environment_summarizer(repo_path: str) -> None:
    """Evaluate EnvironmentSummarizer on a given repository.

    Args:
        repo_path: Path to the repository to analyze
    """
    import time

    repo_path_obj = Path(repo_path)

    if not repo_path_obj.exists():
        print(f"❌ Error: Repository path does not exist: {repo_path}")
        sys.exit(1)

    # Create run directory
    run_dir = create_run_directory(repo_path, "EnvironmentSummarizer")
    print(f"\n📁 Run directory created: {run_dir}")

    # Setup run environment (copy config, save input)
    # Create agent
    agent = EnvironmentSummarizer()
    setup_run_environment(run_dir, repo_path, agent.name)

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
        result = agent.run(str(repo_path_obj.absolute()))
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
    save_execution_results(run_dir, agent, result, execution_time)
    print(f"✅ All results saved to: {run_dir}")
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

    evaluate_environment_summarizer(repo_path)


if __name__ == "__main__":
    main()
