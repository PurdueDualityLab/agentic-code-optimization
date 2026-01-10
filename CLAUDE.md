# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Agentic Code Optimizer** is a LangGraph-based multi-agent framework for code optimization. It provides a declarative system for building AI agents that analyze and optimize code across multiple languages using pluggable LLM providers (Ollama, OpenAI, Anthropic).

**Current Status**: Framework complete, agents awaiting implementation.

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
- Manages agentic loop: Think → Tool Use → Observe
- Handles tool binding, execution, state tracking
- `AgentState`: Tracks messages, tool results, iterations, status

**`providers/` - LLM Provider Abstraction**
- `base.py`: `BaseProvider` abstract class and `ProviderResponse` format
- `registry.py`: `ProviderRegistry` factory for dynamic provider management
- `ollama.py`, `openai.py`, `anthropic.py`: Concrete implementations
- Config-driven instantiation via `ProviderRegistry.create(provider_name)`

**`config/` - Configuration System**
- `parser.py`: `ConfigParser` singleton, lazy-loads from `config.ini`
- `base.py`: `SubSectionParser` ABC for dataclass-based config
- `providers.py`: Config dataclasses for each provider (`OllamaConfig`, `OpenAIConfig`, `AnthropicConfig`)

### State Flow for LangGraph

Agent execution returns state updates in format:
```python
{
    "return_state_field": result,  # From agent.return_state_field
    # ... other state fields
}
```

Agents are designed as LangGraph nodes with state-compatible outputs.

## Common Development Tasks

### Setup & Installation

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Set up config
# Edit config.ini with provider settings
# Create .env for API keys: OPENAI_API_KEY, ANTHROPIC_API_KEY
```

### Code Quality Commands

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/

# All checks together
black src/ tests/ && ruff check src/ tests/ && mypy src/
```

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_base_agent.py::TestAgentCreation

# With coverage
pytest tests/ --cov=src/agentic_optimizer

# Watch mode (requires pytest-watch)
ptw tests/
```

## Creating Custom Agents

**Declarative Pattern:**
```python
from agents.base import BaseAgent
from langchain_core.tools import tool

@tool
async def my_tool(code: str) -> str:
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
agent = MyOptimizationAgent()
result = await agent.execute(
    code="...",
    user_input="Optimize this"
)
# result["my_results"] contains output
```

## Creating Custom Providers

```python
from providers.base import BaseProvider, ProviderResponse
from providers.registry import ProviderRegistry
from config.base import SubSectionParser

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

    async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> ProviderResponse:
        # Implementation
        return ProviderResponse(
            content="...",
            model=self.config.model,
            usage={"tokens": 0}
        )

    async def validate_connection(self) -> bool:
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

**`config.ini` Format:**
```ini
[section_name]
field1 = value1
field2 = value2
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
**Agentic Loop**: Iterative refinement (Think → Tool Use → Observe) with max iteration limits
**State Management**: `AgentState` tracks execution; conversions for LangGraph integration

## Important Files

| File | Purpose |
|------|---------|
| `agents/base.py` | Core agent framework with declarative pattern |
| `providers/registry.py` | Provider factory and management |
| `config/parser.py` | Configuration loading system |
| `config.ini` | Provider configuration and defaults |
| `pyproject.toml` | Dependencies, tool config (black, ruff, mypy, pytest) |
| `requirements.txt` | Pinned dependencies |

## Dependencies

**Core**: `langgraph`, `langchain`, `langchain-core`
**Providers**: `httpx` (Ollama), `openai`, `anthropic`
**Configuration**: `pydantic`, `python-dotenv`, `pyyaml`
**Development**: `pytest`, `pytest-asyncio`, `black`, `ruff`, `mypy`

## Notes

- All agent classes must inherit from `BaseAgent` (imported as `Agent` in many places, check `agents/__init__.py`)
- Tools use `@tool` decorator from `langchain_core.tools`
- Configuration lazy-loads on first access via `ConfigParser.get()`
- Providers support both sync and async, detected automatically
- Use `await agent.execute()` for async execution
- Agent state includes iteration count and max iteration enforcement
- Return state field is configurable per agent via `return_state_field` class attribute
