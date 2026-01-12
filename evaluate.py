"""Evaluation script for agents with simplified structure.

This script demonstrates how to run agents with the new simplified BaseAgent.

Usage:
    python evaluate.py                          # Run on current project
    python evaluate.py <repo_path>              # Run on specific repository
"""

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from agents.summarizers import EnvironmentSummarizer

load_dotenv()

# Initialize logging
_log_dir = Path.cwd() / "logs"
logger = logging.getLogger(__name__)
logger.info("Evaluation script started")


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
    print()

    # Run the agent
    print("RUNNING AGENT...")
    print("-" * 80)

    try:
        logger.info(f"Starting agent execution for repository: {repo_path_obj.absolute()}")
        result = await agent.run(str(repo_path_obj.absolute()))
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
    print(f"  Final Result Length: {len(result) if result else 0} characters")
    print()

    # Display LangGraph output format
    print("LANGGRAPH OUTPUT FORMAT:")
    langgraph_output = agent.get_langgraph_output()
    print(f"  Fields: {list(langgraph_output.keys())}")
    print(f"  Result Key: {agent.return_state_field}")
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
