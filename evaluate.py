"""Generic evaluation script for agents and workflows.

This script can run any agent or workflow defined in the agents/ and workflows/ modules.

Usage:
    python evaluate.py                                      # Show available agents/workflows
    python evaluate.py <agent/workflow_name> <repo_path>    # Run specific agent/workflow

Examples:
    python evaluate.py EnvironmentSummarizerAgent .
    python evaluate.py AnalyzerAgent /path/to/repo
    python evaluate.py orchestrate_summarizers /path/to/repo
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable, Type, Union

from beautilog import logger
from dotenv import load_dotenv

# Load environment variables before importing agents/workflows
load_dotenv()

# Import all agents
from agents import (AnalyzerAgent, BaseAgent, BehaviorSummarizerAgent,
                    BenchmarkAgent, ComponentSummarizerAgent,
                    EnvironmentSummarizerAgent, OptimizerAgent)
from utils import RunManager
# Import all workflows
from workflows import orchestrate_complete_pipeline, orchestrate_summarizers

# Registry of available agents and workflows
AGENTS: dict[str, Type[BaseAgent]] = {
    "AnalyzerAgent": AnalyzerAgent,
    "OptimizerAgent": OptimizerAgent,
    "BehaviorSummarizerAgent": BehaviorSummarizerAgent,
    "ComponentSummarizerAgent": ComponentSummarizerAgent,
    "EnvironmentSummarizerAgent": EnvironmentSummarizerAgent,
    "BenchmarkAgent": BenchmarkAgent,
}

WORKFLOWS: dict[str, Callable] = {
    "orchestrate_complete_pipeline": orchestrate_complete_pipeline,
    "orchestrate_summarizers": orchestrate_summarizers,
}


async def evaluate_agent(agent_class: Type[BaseAgent], repo_path: str) -> None:
    """Evaluate an agent on a given repository.

    Args:
        agent_class: The agent class to instantiate and run
        repo_path: Path to the repository to analyze
    """
    repo_path_obj = Path(repo_path)

    if not repo_path_obj.exists():
        logger.error(f"Repository path does not exist: {repo_path}")
        sys.exit(1)

    # Create agent
    agent = agent_class()

    # Create run manager and directory
    run_manager = RunManager()
    run_dir = run_manager.create_run_dir(repo_path, agent.name)
    logger.info(f"Run directory created: {run_dir}")

    # Setup run environment
    run_manager.save_config(Path.cwd() / "config.ini")
    run_manager.save_input(repo_path, agent.name)
    logger.update_log_file_path(run_dir / "execution.log")

    logger.info("=" * 80)
    logger.info(f"{agent.name.upper()} EVALUATION")
    logger.info("=" * 80)

    # Display agent configuration
    logger.info("AGENT CONFIGURATION:")
    logger.info(f"  Name: {agent.name}")
    logger.info(f"  Provider: {agent.llm.__class__.__name__}")
    logger.info(f"  Temperature: {agent.temperature}")
    logger.info(f"  Max Iterations: {agent.max_iterations}")
    logger.info(f"  Tools: {len(agent.tools)}")
    logger.info(f"  Return State Field: {agent.return_state_field}")

    # Display analysis target
    logger.info("ANALYSIS TARGET:")
    logger.info(f"  Repository Path: {repo_path_obj.absolute()}")
    logger.info(f"  Path Exists: {repo_path_obj.exists()}")
    logger.info(f"  Is Directory: {repo_path_obj.is_dir()}")
    logger.info(f"  Run Directory: {run_dir}")

    # Run the agent (async execution)
    logger.info("RUNNING AGENT...")
    logger.info("-" * 80)

    try:
        logger.info(f"Starting agent execution for repository: {repo_path_obj.absolute()}")
        start_time = time.time()
        if agent_class is BenchmarkAgent:
            benchmark_dir = run_dir / "benchmark"
            payload = {
                "command_env": "BENCHMARK_CMD",
                "workdir": str(repo_path_obj.absolute()),
                "output_dir": str(benchmark_dir),
                "render_charts": True,
            }
            result = await agent.run(json.dumps(payload))
        else:
            result = await agent.run(str(repo_path_obj.absolute()))
        execution_time = time.time() - start_time
        logger.info(f"Agent execution completed successfully, result length: {len(result) if result else 0}")
        logger.info(f"RESULT:\n{result}")
    except Exception as e:
        logger.error(f"Agent execution failed: {str(e)}", exc_info=True)
        sys.exit(1)

    logger.info("-" * 80)

    # Execution summary
    logger.info("EXECUTION SUMMARY:")
    logger.info(f"  Final Result Length: {len(result) if result else 0} characters")
    logger.info(f"  Execution Time: {execution_time:.2f} seconds")

    # Save execution results to run directory
    run_manager.save_response(result)
    metrics = {
        "result_length": len(result) if result else 0,
        "execution_time_seconds": execution_time,
        "max_iterations": agent.max_iterations,
        "temperature": agent.temperature,
        "provider": agent.llm.__class__.__name__,
        "agent_name": agent.name,
    }
    run_manager.save_metrics(metrics)

    logger.info(f"All results saved to: {run_dir}")
    run_info = run_manager.get_run_info()
    logger.info(f"Artifacts: {', '.join(run_info['artifacts'])}")

    logger.info("=" * 80)
    logger.info("EVALUATION COMPLETE")
    logger.info("=" * 80)


async def evaluate_workflow(workflow_func: Callable, repo_path: str) -> None:
    """Evaluate a workflow on a given repository.

    Args:
        workflow_func: The workflow function to execute
        repo_path: Path to the repository to analyze
    """
    repo_path_obj = Path(repo_path)

    if not repo_path_obj.exists():
        logger.error(f"Repository path does not exist: {repo_path}")
        sys.exit(1)

    workflow_name = workflow_func.__name__

    # Create run manager and directory
    run_manager = RunManager()
    run_dir = run_manager.create_run_dir(repo_path, workflow_name)
    logger.info(f"Run directory created: {run_dir}")

    # Setup run environment
    run_manager.save_config(Path.cwd() / "config.ini")
    run_manager.save_input(repo_path, workflow_name)
    logger.update_log_file_path(run_dir / "execution.log")

    logger.info("=" * 80)
    logger.info(f"{workflow_name.upper()} EVALUATION")
    logger.info("=" * 80)

    # Display analysis target
    logger.info("ANALYSIS TARGET:")
    logger.info(f"  Repository Path: {repo_path_obj.absolute()}")
    logger.info(f"  Path Exists: {repo_path_obj.exists()}")
    logger.info(f"  Is Directory: {repo_path_obj.is_dir()}")
    logger.info(f"  Run Directory: {run_dir}")

    # Run the workflow
    logger.info("RUNNING WORKFLOW...")
    logger.info("-" * 80)

    try:
        logger.info(f"Starting workflow execution for repository: {repo_path_obj.absolute()}")
        start_time = time.time()
        result = await workflow_func(str(repo_path_obj.absolute()))
        execution_time = time.time() - start_time
        logger.info(f"Workflow execution completed successfully")
        logger.info(f"RESULT:\n{result}")
    except Exception as e:
        logger.error(f"Workflow execution failed: {str(e)}", exc_info=True)
        sys.exit(1)

    logger.info("-" * 80)

    # Execution summary
    logger.info("EXECUTION SUMMARY:")
    logger.info(f"  Execution Time: {execution_time:.2f} seconds")

    # Save execution results to run directory
    run_manager.save_response(str(result))
    metrics = {
        "execution_time_seconds": execution_time,
        "workflow_name": workflow_name,
    }
    run_manager.save_metrics(metrics)

    logger.info(f"All results saved to: {run_dir}")
    run_info = run_manager.get_run_info()
    logger.info(f"   Artifacts: {', '.join(run_info['artifacts'])}")

    logger.info("=" * 80)
    logger.info("EVALUATION COMPLETE")
    logger.info("=" * 80)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    # Get available options for help text
    agent_names = sorted(AGENTS.keys())
    workflow_names = sorted(WORKFLOWS.keys())

    parser = argparse.ArgumentParser(
        description="Generic evaluation script for agents and workflows.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Available Agents:
{chr(10).join(f'  - {name}' for name in agent_names)}

Available Workflows:
{chr(10).join(f'  - {name}' for name in workflow_names)}

Examples:
  python evaluate.py EnvironmentSummarizerAgent .
  python evaluate.py AnalyzerAgent /path/to/repo
  python evaluate.py orchestrate_summarizers /path/to/repo
  python evaluate.py --list
        """,
    )

    parser.add_argument(
        "agent_or_workflow",
        nargs="?",
        help="Name of the agent or workflow to run",
    )

    parser.add_argument(
        "repo_path",
        nargs="?",
        help="Path to the repository to analyze",
    )

    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List all available agents and workflows",
    )

    return parser


def main() -> None:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Handle --list flag
    if args.list:
        logger.info("=" * 80)
        logger.info("AVAILABLE AGENTS AND WORKFLOWS")
        logger.info("=" * 80)
        logger.info("")
        logger.info("AGENTS:")
        for agent_name in sorted(AGENTS.keys()):
            logger.info(f"  - {agent_name}")
        logger.info("")
        logger.info("WORKFLOWS:")
        for workflow_name in sorted(WORKFLOWS.keys()):
            logger.info(f"  - {workflow_name}")
        logger.info("")
        logger.info("=" * 80)
        sys.exit(0)

    # Check required arguments
    if not args.agent_or_workflow or not args.repo_path:
        logger.error("Missing required arguments")
        parser.print_help()
        sys.exit(1)

    agent_or_workflow_name = args.agent_or_workflow
    repo_path = args.repo_path

    # Check if it's an agent
    if agent_or_workflow_name in AGENTS:
        agent_class = AGENTS[agent_or_workflow_name]
        logger.info(f"Evaluating agent: {agent_or_workflow_name}")
        asyncio.run(evaluate_agent(agent_class, repo_path))

    # Check if it's a workflow
    elif agent_or_workflow_name in WORKFLOWS:
        workflow_func = WORKFLOWS[agent_or_workflow_name]
        logger.info(f"Evaluating workflow: {agent_or_workflow_name}")
        asyncio.run(evaluate_workflow(workflow_func, repo_path))

    # Invalid name
    else:
        logger.error(f"Unknown agent or workflow: {agent_or_workflow_name}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
