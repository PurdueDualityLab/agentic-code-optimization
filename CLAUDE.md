# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Agentic Code Optimizer** is a LangGraph-based multi-agent framework for code optimization. It provides a declarative system for building AI agents that analyze and optimize code across multiple languages using pluggable LLM providers (Ollama, OpenAI, Anthropic).

**Requirements**: Python 3.11+ (required for built-in `tomllib` support)

**Current Status**: Framework complete with working agents, logging, metrics tracking, and run management.

## Architecture

### Two-Phase Optimization Pattern

```
Input Code
    ↓
PHASE 1: SUMMARIZATION (Parallel)
├─ Environment Summary Agent
├─ Behavior Summary Agent
├─ Component Summary Agent
    ↓
PHASE 2: OPTIMIZATION (Sequential)
├─ Analyzer Agent
├─ Optimization Agent
    ↓
Output: Optimized Code + Recommendations
```

### Core Modules

**`agents/` - Agent Framework**
- `base.py`: `BaseAgent` abstract class implementing declarative pattern with `__new__` processing
- Manages agentic loop using LangGraph: Think (LLM Call) → Tool Use → Observe
- Synchronous execution (not async) for better logging and visibility
- Handles tool binding, execution, state tracking, iteration counting
- Tracks: `iteration_count` (LLM calls only), `tools_used_count` (total tool executions), `tools_used_names` (unique tools)
- Built-in logging at INFO level for major steps, DEBUG level for detailed state inspection
- **Middleware Support**: 7 built-in middleware for enhanced capabilities (see docs/MIDDLEWARE.md)
  - Summarization: Auto-compress conversation history
  - To-do list: Task planning for multi-step operations
  - LLM tool selector: Intelligent tool filtering
  - Tool retry: Automatic retry with exponential backoff
  - Context editing: Automatic context cleanup
  - Shell tool: Persistent shell session
  - File search: Glob and regex search over filesystem

**`providers/` - LLM Provider Abstraction**
- `base.py`: `BaseProvider` abstract class and `ProviderResponse` format
- `registry.py`: `ProviderRegistry` factory for dynamic provider management
- `ollama.py`, `openai.py`, `anthropic.py`: Concrete implementations
- Config-driven instantiation via `ProviderRegistry.create(provider_name)`

**`config/` - Configuration System**
- `parser.py`: `ConfigParser` singleton, lazy-loads from `config.ini`
- `base.py`: `SubSectionParser` ABC for dataclass-based config
- `providers.py`: Config dataclasses for each provider (`OllamaConfig`, `OpenAIConfig`, `AnthropicConfig`)

**`tools/` - Code Analysis Tools**
- `behavior.py`: Analyzes code behavior, logic, patterns, and execution flow
- `component.py`: Identifies structure, functions, classes, and components
- `environment.py`: Analyzes dependencies, imports, and environment setup

**`utils/` - Utilities (NEW)**
- `metrics.py`: `ExecutionMetrics`, `Trace`, `ObservabilityManager` for execution tracking
- `runs.py`: `RunManager` for managing execution artifacts and run directories

### Execution Flow & Run Management

When you run `python evaluate.py`:

1. **Run Directory Created**: `runs/{agent_name}_{YYYYMMDD_HHMMSS}/`
2. **Artifacts Saved**:
   - `config.ini` - Copy of configuration used
   - `input.txt` - Execution parameters (timestamp, agent, repo path, etc.)
   - `response.txt` - Complete agent response
   - `metrics.json` - Execution metrics (LLM iterations, tools used, timing, provider)
   - `state.json` - Agent state snapshot (messages count, tools used, LangGraph output)
   - `summary.md` - Human-readable markdown summary

### Logging System

- **Backend**: Beautilog (logs to console + file simultaneously)
- **Log Files**: `logs/agent.log` and `logs/evaluate.log`
- **Levels**:
  - **INFO**: Major steps (agent start/end, LLM calls, tool execution, graph compilation)
  - **DEBUG**: Detailed state inspection (state dicts, messages, tool results)
  - **ERROR**: Failures and exceptions with full traceback

### State Flow for LangGraph

Agent execution in `run()` method:
1. Creates `StateGraph(MessagesState)` with LLM call and tool nodes
2. Routes based on whether LLM generated tool calls
3. Returns state in format:
```python
{
    "return_state_field": result,  # From agent.return_state_field
    "return_state_field_state": {
        "messages": [...],         # Full message history
        "iterations": count,       # LLM call count
        "tools_used_count": total, # Total tool executions
        "tools_used_names": [...], # List of tools used
        "unique_tools_count": n    # Count of unique tools
    }
}
```

## Common Development Tasks

### Setup & Installation

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up config
# Copy .env.example to .env and fill in API keys
cp .env.example .env
# Edit config.ini with provider settings
```

### Code Quality Commands

```bash
# Format code
black agents/ config/ providers/ tools/ utils/ evaluate.py

# Lint
ruff check agents/ config/ providers/ tools/ utils/ evaluate.py

# Type check
mypy agents/ config/ providers/ tools/ utils/ evaluate.py

# All checks together
black agents/ config/ providers/ tools/ utils/ evaluate.py && \
ruff check agents/ config/ providers/ tools/ utils/ evaluate.py && \
mypy agents/ config/ providers/ tools/ utils/ evaluate.py
```

### Running the Evaluation

```bash
# Run on current project
python evaluate.py

# Run on specific repository
python evaluate.py /path/to/repo

# View results
ls -la runs/EnvironmentSummarizer_*/
cat runs/EnvironmentSummarizer_*/summary.md
```

## Creating Custom Agents

**Declarative Pattern:**
```python
from agents.base import BaseAgent
from langchain_core.tools import tool

@tool
def my_tool(code: str) -> str:
    """Tool description and usage."""
    return "result"

class MyOptimizationAgent(BaseAgent):
    prompt = """You are an expert code optimizer.

    Analyze code and provide optimizations."""

    tools = [my_tool]

    return_state_field = "my_results"

    # Optional overrides
    max_iterations = 8
    temperature = 0.3
    provider_name = "anthropic"  # Override default
```

**Using the Agent:**
```python
from agents import BaseAgent

agent = MyOptimizationAgent()
result = agent.run("code to analyze")  # Synchronous
# result contains the final response
# Access metrics via: agent.iteration_count, agent.tools_used_count
```

## Creating Custom Providers

```python
from providers.base import BaseProvider, ProviderResponse
from providers.registry import ProviderRegistry
from config.base import SubSectionParser
from dataclasses import dataclass

# 1. Define config
@dataclass
class CustomConfig(SubSectionParser):
    SECTION = "custom"
    api_key: str
    model: str
    # ... other fields

# 2. Implement provider
class CustomProvider(BaseProvider):
    def __init__(self, config: CustomConfig):
        self.config = config

    def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> ProviderResponse:
        # Implementation
        return ProviderResponse(
            content="...",
            model=self.config.model,
            usage={"tokens": 0}
        )

    def validate_connection(self) -> bool:
        # Connection validation
        pass

    def get_provider_name(self) -> str:
        return "custom"

# 3. Register
ProviderRegistry.register("custom", CustomProvider, CustomConfig)

# 4. Add to config.ini
# [custom]
# api_key = ...
# model = ...
```

## Configuration

**`.env` File Format:**
```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_ORGANIZATION_ID=org-...

# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...

# Ollama (typically no API key needed, runs locally)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=devstral-2:123b

# Logging
LOG_LEVEL=INFO

# Application
DEFAULT_PROVIDER=ollama
MAX_ITERATIONS=30
TIMEOUT=60
VERBOSE=true
```

**`config.ini` Format:**
```ini
[agents]
max_iterations = 30
default_provider = ollama
temperature = 0.7

# Middleware (optional) - see docs/MIDDLEWARE.md for details
enable_summarization = false
enable_todo_list = false
enable_llm_tool_selector = false
enable_tool_retry = false
enable_context_editing = false
enable_shell_tool = false
enable_file_search = false

[ollama]
base_url = http://localhost:11434
model = devstral-2:123b
temperature = 0.7

[openai]
api_key = ${OPENAI_API_KEY}
model = gpt-5
temperature = 0.7

[anthropic]
api_key = ${ANTHROPIC_API_KEY}
model = claude-3-5-sonnet-20241022
temperature = 0.7
```

**Loading:**
```python
from config.parser import ConfigParser
from config.providers import OllamaConfig

ConfigParser.load()  # Loads from config.ini in project root
config = ConfigParser.get(OllamaConfig)
```

**Priority**: Environment variables → INI values → Code defaults

## Key Design Patterns

**Declarative Agents**: Class attributes define behavior; `__new__` validates and binds tools
**Factory Pattern**: `ProviderRegistry` creates providers from config
**Configuration Pattern**: Dataclass-based config with INI mapping via `SubSectionParser`
**Agentic Loop**: LangGraph-based workflow (Think → Tool Use → Observe) with max iteration limits
**State Management**: Message-based state; conversions for LangGraph integration
**Run Management**: `RunManager` handles execution artifacts and directory organization
**Logging**: Beautilog for beautiful terminal + file logging simultaneously

## Important Files

| File | Purpose |
|------|---------|
| `agents/base.py` | Core agent framework with LangGraph integration and middleware support |
| `agents/summarizers/` | Specialized summarizer agents |
| `providers/registry.py` | Provider factory and management |
| `config/parser.py` | Configuration loading system |
| `config/agents.py` | Agent configuration including middleware settings |
| `utils/runs.py` | Run directory and artifact management |
| `utils/metrics.py` | Execution metrics and observability |
| `evaluate.py` | Main evaluation/execution script |
| `config.ini` | Provider and middleware configuration |
| `.env.example` | Environment variables template |
| `requirements.txt` | Pinned dependencies |
| `docs/MIDDLEWARE.md` | **Complete middleware guide and examples** |
| `examples/middleware_example.py` | Example agent using middleware |

## Dependencies

**Core**: `langgraph`, `langchain`, `langchain-core`
**Providers**: `httpx` (Ollama), `openai`, `anthropic`
**Configuration**: `pydantic`, `python-dotenv`, `pyyaml`
**Logging**: `beautilog`
**Development**: `pytest`, `pytest-asyncio`, `black`, `ruff`, `mypy`

## Important Notes

- All agent classes must inherit from `BaseAgent`
- Agent `run()` method is **synchronous** (not async) for better logging visibility
- Tools use `@tool` decorator from `langchain_core.tools`
- Configuration lazy-loads on first access via `ConfigParser.get()`
- Iteration count only increments on **LLM calls**, not tool executions
- Tools used are tracked in `tools_used_count` (total) and `tools_used_names` (unique)
- Every execution creates a run directory with full artifacts for reproducibility
- Beautilog logs to both terminal (colored) and file simultaneously
- Use `logger.debug()` for detailed state inspection during development
- Return state field is configurable per agent via `return_state_field` class attribute

## Recent Changes

### 2025-01-22: Middleware Support
- ✅ Added 7 built-in middleware from LangChain for enhanced agent capabilities
- ✅ Configuration-driven middleware via `config.ini` [agents] section
- ✅ Comprehensive documentation in `docs/MIDDLEWARE.md`
- ✅ Example implementation in `examples/middleware_example.py`
- ✅ Middleware: Summarization, To-do list, LLM tool selector, Tool retry, Context editing, Shell tool, File search

### 2025-01-12: Framework Improvements
- ✅ Consolidated `agentic_logging/` and `observability/` modules into `utils/`
- ✅ Replaced async execution with synchronous `run()` for better logging
- ✅ Added comprehensive debug logging for state inspection
- ✅ Implemented `RunManager` for execution artifact management
- ✅ Added metrics tracking: `tools_used_count`, `iteration_count` (LLM calls only), `tools_used_names`
- ✅ Integrated beautilog for beautiful terminal + file logging
- ✅ Created run directory structure with config, input, response, metrics, state, summary
- ✅ Removed unused `callbacks/` module
- ✅ Created `.env.example` for easy setup
