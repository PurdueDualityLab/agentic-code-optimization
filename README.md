# Agentic Code Optimizer

A multi-agent code optimization system built with LangGraph that analyzes and optimizes code across multiple languages using AI agents.

## Features

- **Multi-Phase Optimization**: Two-phase architecture with parallel summarization and sequential optimization
- **Provider Agnostic**: Support for Ollama (local), OpenAI, Anthropic, and custom providers with easy switching
- **Multi-Language**: Optimize Python, JavaScript, TypeScript, Java, and more
- **Extensible Architecture**: Clean base classes for easy agent and provider development
- **Parallel Processing**: LangGraph-based workflow with parallel summarization agents
- **Execution Tracking**: Comprehensive metrics and artifact management with RunManager
- **Beautiful Logging**: Beautilog integration for terminal + file logging simultaneously
- **Comprehensive Analysis**:
  - Performance optimization (algorithmic efficiency, memory usage, execution time)
  - Code quality improvements (readability, maintainability, best practices)
  - Security analysis (vulnerabilities, input validation, secure coding)

## Architecture

### Phase 1: Code Summarization (Parallel)
Three specialized agents run in parallel to analyze different aspects of code:
- **Environment Summary Agent** - Analyzes dependencies, imports, and environment setup
- **Behavior Summary Agent** - Understands code behavior, logic flow, and patterns
- **Component Summary Agent** - Identifies structure, functions, classes, and components

### Phase 2: Code Optimization (Sequential)
- **Analyzer Agent** - Reviews summaries and identifies optimization opportunities
- **Optimization Agent** - Applies optimizations based on analysis and generates improved code

## Project Structure

```
agentic-code-optimization/
├── agents/                      # Agent framework
│   ├── base.py                 # BaseAgent abstract class
│   ├── __init__.py
│   └── summarizers/            # Specialized summarizer agents
│       ├── environment.py       # Environment Summary Agent
│       ├── behavior.py          # Behavior Summary Agent
│       ├── component.py         # Component Summary Agent
│       └── __init__.py
├── providers/                   # LLM provider implementations
│   ├── base.py                 # BaseProvider abstract class
│   ├── registry.py             # ProviderRegistry (factory pattern)
│   ├── ollama.py               # Ollama local provider
│   ├── openai.py               # OpenAI provider
│   ├── anthropic.py            # Anthropic Claude provider
│   └── __init__.py
├── config/                      # Configuration system
│   ├── base.py                 # SubSectionParser ABC
│   ├── parser.py               # ConfigParser singleton
│   ├── providers.py            # Provider configurations
│   └── __init__.py
├── tools/                       # Code analysis tools
│   ├── environment.py           # Dependency/environment analysis
│   ├── behavior.py              # Logic/pattern analysis
│   ├── component.py             # Structure analysis
│   └── __init__.py
├── utils/                       # Utilities (NEW)
│   ├── metrics.py              # ExecutionMetrics, Trace, ObservabilityManager
│   ├── runs.py                 # RunManager for artifact management
│   └── __init__.py
├── evaluate.py                 # Main evaluation script
├── config.ini                  # Configuration file
├── .env.example                # Environment variables template
├── CLAUDE.md                   # Claude Code guidance
├── README.md
├── requirements.txt
└── .gitignore
```

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd agentic-code-optimization

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Setup

1. **Copy environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Configure API Keys** - Edit `.env` with your credentials:
   ```bash
   # OpenAI
   OPENAI_API_KEY=sk-...
   OPENAI_ORGANIZATION_ID=org-...

   # Anthropic Claude
   ANTHROPIC_API_KEY=sk-ant-...

   # Ollama (local, no API key needed)
   OLLAMA_BASE_URL=http://localhost:11434
   ```

3. **Configure Provider** - Edit `config.ini`:
   ```ini
   [agents]
   max_iterations = 30
   default_provider = ollama
   temperature = 0.7

   [ollama]
   base_url = http://localhost:11434
   model = devstral-2:123b

   [openai]
   api_key = ${OPENAI_API_KEY}
   model = gpt-5

   [anthropic]
   api_key = ${ANTHROPIC_API_KEY}
   model = claude-3-5-sonnet-20241022
   ```

4. **(Optional) Use Ollama locally**:
   ```bash
   # Install Ollama from https://ollama.ai
   ollama pull devstral-2:123b
   ```

### Usage

```bash
# Run on current project
python evaluate.py

# Run on specific repository
python evaluate.py /path/to/repo
```

**Python API:**
```python
from agents.summarizers import EnvironmentSummarizer

# Create agent
agent = EnvironmentSummarizer()

# Execute (synchronous)
result = agent.run("/path/to/code")

# Access metrics
print(f"LLM Iterations: {agent.iteration_count}")
print(f"Tools Used: {agent.tools_used_count}")
print(f"Tool Names: {agent.tools_used_names}")

# Get LangGraph output
output = agent.get_langgraph_output()
print(output)
```

## Execution & Run Management

### Run Directories

When you execute `python evaluate.py`, the system creates a timestamped run directory with all artifacts:

```
runs/
└── EnvironmentSummarizer_20250112_120000/
    ├── config.ini           # Copy of configuration used
    ├── input.txt            # Execution parameters
    ├── response.txt         # Agent response
    ├── metrics.json         # Execution metrics
    ├── state.json           # Agent state snapshot
    └── summary.md           # Human-readable summary
```

### Metrics Tracked

- **LLM Iterations**: Count of LLM calls (not tool executions)
- **Tools Used**: Total number of tool executions
- **Unique Tools**: List of distinct tools used
- **Execution Time**: Total runtime in seconds
- **Provider**: Which LLM provider was used

## Logging System

The system uses **Beautilog** for beautiful terminal + file logging:

- **Console**: Colored output for easy readability
- **Files**: `logs/agent.log` and `logs/evaluate.log`
- **Levels**:
  - `INFO`: Major steps (agent start/end, LLM calls, tool execution)
  - `DEBUG`: Detailed state inspection (state dicts, messages, results)
  - `ERROR`: Failures with full traceback

```bash
# View logs
tail -f logs/agent.log
tail -f logs/evaluate.log
```

## Configuration

### .env File

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-key-here
OPENAI_ORGANIZATION_ID=org-your-id-here

# Anthropic Claude Configuration
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Ollama Configuration (local, no keys needed)
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

### config.ini Structure

```ini
[agents]
max_iterations = 30
default_provider = ollama
temperature = 0.7

[ollama]
base_url = http://localhost:11434
model = devstral-2:123b
temperature = 0.7
max_tokens = 8192
timeout = 60

[openai]
api_key = ${OPENAI_API_KEY}
model = gpt-5
temperature = 0.7
max_tokens = 4096
timeout = 60

[anthropic]
api_key = ${ANTHROPIC_API_KEY}
model = claude-3-5-sonnet-20241022
temperature = 0.7
max_tokens = 4096
timeout = 60
```

## Development

### Code Quality

```bash
# Format code
black agents/ config/ providers/ tools/ utils/ evaluate.py

# Lint
ruff check agents/ config/ providers/ tools/ utils/ evaluate.py

# Type check
mypy agents/ config/ providers/ tools/ utils/ evaluate.py

# All checks
black agents/ config/ providers/ tools/ utils/ evaluate.py && \
  ruff check agents/ config/ providers/ tools/ utils/ evaluate.py && \
  mypy agents/ config/ providers/ tools/ utils/ evaluate.py
```

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_base_agent.py::TestAgent -v

# With coverage
pytest tests/ --cov=agents --cov=providers --cov=config --cov=utils
```

## Extending the System

### Creating a Custom Agent

Agents use a **declarative pattern** with class attributes:

```python
from agents.base import BaseAgent
from langchain_core.tools import tool

# Define tools
@tool
def analyze_complexity(code: str) -> str:
    """Analyze code complexity."""
    # Implementation
    return "analysis result"

# Define agent
class MyAnalysisAgent(BaseAgent):
    prompt = """You are an expert code analyzer.

    Analyze code structure, complexity, and quality."""

    tools = [analyze_complexity]

    return_state_field = "my_analysis"

    # Optional overrides
    max_iterations = 8
    temperature = 0.3
    provider_name = "anthropic"

# Use the agent
agent = MyAnalysisAgent()
result = agent.run("code to analyze")
print(result)

# Access metrics
print(f"LLM calls: {agent.iteration_count}")
print(f"Tools used: {agent.tools_used_count}")
```

**Key Agent Attributes:**
- `prompt` - System prompt (required)
- `tools` - List of tools available to agent (required)
- `return_state_field` - State field to store results (required)
- `max_iterations` - Max agentic loop iterations (default: from config)
- `temperature` - LLM temperature (default: from config)
- `provider_name` - Which provider to use (default: from config)

**Important Notes:**
- Agent `run()` method is **synchronous** (not async)
- Iteration count tracks only **LLM calls**, not tool executions
- Tool usage is tracked in `tools_used_count` and `tools_used_names`
- Every execution creates a run directory with artifacts

### Creating a Custom Provider

```python
from providers.base import BaseProvider, ProviderResponse
from providers.registry import ProviderRegistry
from config.base import SubSectionParser
from dataclasses import dataclass

# 1. Define config
@dataclass
class CustomConfig(SubSectionParser):
    SECTION = "custom"
    api_url: str
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096

# 2. Implement provider
class CustomProvider(BaseProvider):
    def __init__(self, config: CustomConfig):
        self.config = config

    def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> ProviderResponse:
        # Call your API
        response = self._call_api(system_prompt, user_prompt)

        return ProviderResponse(
            content=response["output"],
            model=self.config.model,
            usage={"tokens": response.get("tokens", 0)}
        )

    def validate_connection(self) -> bool:
        try:
            # Test API connection
            return True
        except:
            return False

    def get_provider_name(self) -> str:
        return "custom"

# 3. Register provider
ProviderRegistry.register("custom", CustomProvider, CustomConfig)

# 4. Add to config.ini
# [custom]
# api_url = https://api.example.com
# api_key = your-key
# model = your-model
```

## Workflow Execution

```
┌─────────────────────────────────────────────┐
│              Input Code                     │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│   PHASE 1: SUMMARIZATION (Parallel)         │
├─────────────────────────────────────────────┤
│  Environment Summary Agent                  │
│  Behavior Summary Agent                     │
│  Component Summary Agent                    │
│         (run simultaneously)                │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│     Combine Summaries                       │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│   PHASE 2: OPTIMIZATION (Sequential)        │
├─────────────────────────────────────────────┤
│  Analyzer Agent                             │
│    ↓                                        │
│  Optimization Agent                         │
│    ↓                                        │
│  Update Repository                          │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│    Optimized Code + Report + Artifacts      │
└─────────────────────────────────────────────┘
```

## Design Patterns

### Declarative Agent Pattern
Define agents using class attributes instead of method overrides:
```python
class MyAgent(BaseAgent):
    prompt = "..."           # System prompt
    tools = [...]            # Available tools
    return_state_field = "..." # Result field name
```

### Provider Registry Pattern
Dynamically create and manage providers:
```python
from providers.registry import ProviderRegistry

# Create from config
provider = ProviderRegistry.create("ollama")

# Register custom provider
ProviderRegistry.register("custom", CustomProvider)

# Validate connection
is_valid = ProviderRegistry.validate_provider("openai")
```

### Configuration Pattern
Dataclass-based configuration with INI mapping:
```python
from config.parser import ConfigParser
from config.providers import OllamaConfig

ConfigParser.load()
config = ConfigParser.get(OllamaConfig)
```

### RunManager Pattern
Manage execution artifacts and run directories:
```python
from utils import RunManager

run_manager = RunManager()
run_dir = run_manager.create_run_dir(repo_path, agent.name)
run_manager.save_config(config_path)
run_manager.save_response(result)
run_manager.save_metrics(metrics)
run_manager.save_state(agent)
```

### Agentic Loop
Continuous refinement pattern: Think → Tool Use → Observe
```
1. Think: LLM processes context with available tools
2. Tool Use: LLM calls tools and gets results
3. Observe: Tool results fed back to LLM
4. Repeat: Until no tool calls or max_iterations reached
```

## Supported Languages

- Python
- JavaScript / TypeScript
- Java
- C / C++
- Go
- Rust
- And more...

## Performance Considerations

- **Parallel Summarization**: Three agents run concurrently in Phase 1 for faster analysis
- **Provider Flexibility**: Choose between local (Ollama) for privacy or cloud providers for higher quality
- **Configurable Timeouts**: Adjust timeout settings based on your LLM provider and code complexity
- **Synchronous Execution**: Cleaner logging and debugging with synchronous `run()` method

## Security & Privacy

- **Local Processing**: Use Ollama for complete local code analysis without sending data to external services
- **Provider Abstraction**: Easily switch providers based on your security requirements
- **No Code Storage**: By default, code is not persisted unless explicitly configured
- **Input Validation**: All inputs are validated before processing
- **Environment Variables**: Sensitive API keys stored in `.env`, never in code or config

## Roadmap

- [ ] Web UI for code optimization
- [ ] Database backend for code versioning
- [ ] Batch processing for multiple files
- [ ] Custom optimization rules engine
- [ ] Integration with popular IDEs (VS Code, PyCharm)
- [ ] Pre-commit hooks for automatic optimization
- [ ] Performance benchmarking framework
- [ ] Multi-model ensemble optimization

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please see [CLAUDE.md](CLAUDE.md) for development guidelines and architecture details.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Current Status (2025-01-12)

**Recently Implemented:**
- ✅ Agent framework with LangGraph integration
- ✅ Synchronous execution with comprehensive logging
- ✅ Provider abstraction (Ollama, OpenAI, Anthropic)
- ✅ Configuration system (INI-based with .env support)
- ✅ Tool binding and execution with metrics tracking
- ✅ RunManager for execution artifact management
- ✅ Beautilog integration for terminal + file logging
- ✅ Consolidated utils module (metrics + runs management)
- ✅ Execution metrics (iteration_count, tools_used_count, tools_used_names)
- ✅ Run directory structure with automatic artifact storage

**Specialized Agents:**
- ✅ EnvironmentSummarizer
- ✅ BehaviorSummarizer
- ✅ ComponentSummarizer

**Code Analysis Tools:**
- ✅ Environment analysis (dependencies, imports)
- ✅ Behavior analysis (logic, patterns, execution flow)
- ✅ Component analysis (structure, functions, classes)

**Next Phase:**
- [ ] Analyzer Agent
- [ ] Optimization Agent
- [ ] Multi-agent orchestration workflows
- [ ] Comprehensive test suite

## Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- LLM providers: [Ollama](https://ollama.ai), [OpenAI](https://openai.com), [Anthropic](https://anthropic.com)
- Logging: [Beautilog](https://github.com/jmoore914/beautilog)
