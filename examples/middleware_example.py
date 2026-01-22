"""Example demonstrating middleware usage with BaseAgent.

This example shows how to enable and configure different middleware
components via config.ini to enhance agent capabilities.
"""

from agents.base import BaseAgent
from langchain_core.tools import tool


# Define a simple tool for demonstration
@tool
def get_weather(location: str) -> str:
    """Get weather for a location."""
    return f"Weather in {location}: Sunny, 72°F"


@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {e}"


class MiddlewareExampleAgent(BaseAgent):
    """Example agent demonstrating middleware capabilities.

    To enable middleware, update config.ini [agents] section:

    # Enable summarization to manage long conversations
    enable_summarization = true
    summarization_trigger_tokens = 4000
    summarization_keep_messages = 20

    # Enable to-do list for multi-step tasks
    enable_todo_list = true

    # Enable LLM tool selector for large tool sets
    enable_llm_tool_selector = true
    tool_selector_max_tools = 3
    tool_selector_always_include = get_weather

    # Enable tool retry for robust execution
    enable_tool_retry = true
    tool_retry_max_retries = 3

    # Enable context editing for very long conversations
    enable_context_editing = true
    context_edit_trigger_tokens = 100000

    # Enable shell tool for command execution
    enable_shell_tool = true
    shell_workspace_root = /workspace

    # Enable file search for codebase exploration
    enable_file_search = true
    file_search_root_path = /workspace
    """

    prompt = """You are a helpful assistant with access to various tools.

Use the available tools to help the user with their requests.
Be concise and accurate in your responses."""

    tools = [
        get_weather,
        calculate,
    ]

    return_state_field = "result"


async def main():
    """Run the example agent with middleware."""
    print("=" * 80)
    print("Middleware Example Agent")
    print("=" * 80)
    print()

    # Create agent (middleware configured via config.ini)
    agent = MiddlewareExampleAgent()

    print(f"Agent: {agent.name}")
    print(f"Provider: {agent.provider_name}")
    print(f"Tools: {len(agent.tools)}")
    print()

    # Example query
    query = "What's the weather in San Francisco? Also calculate 15 * 8."

    print(f"Query: {query}")
    print()
    print("-" * 80)

    # Run agent
    result = await agent.run(query)

    print("-" * 80)
    print()
    print("Result:")
    print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
