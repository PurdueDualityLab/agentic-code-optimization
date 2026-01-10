# Agentic Code Optimizer

A multi-agent code optimization system built with LangGraph that analyzes and optimizes code across multiple languages using AI agents.

## Features

- **Multi-Phase Optimization**: Two-phase architecture with parallel summarization and sequential optimization
- **Provider Agnostic**: Support for Ollama (local), OpenAI, Anthropic, and custom providers with easy switching
- **Multi-Language**: Optimize Python, JavaScript, TypeScript, Java, and more
- **Extensible Architecture**: Clean base classes for easy agent and provider development
- **Parallel Processing**: LangGraph-based workflow with parallel summarization agents
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
│   ├── examples.py             # Example agents and tools
│   └── __init__.py
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
├── tests/                       # Unit and integration tests
├── config.ini                   # Configuration file
├── CLAUDE.md                    # Claude Code guidance
├── README.md
├── requirements.txt
├── pyproject.toml
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

# Install in development mode
pip install -e .
```

### Setup

1. **Configure Provider** - Edit `config.ini`:
   ```ini
   [ollama]
   base_url = http://localhost:11434
   model = llama2:7b

   [openai]
   api_key = your-key-here
   model = gpt-4

   [anthropic]
   api_key = your-key-here
   model = claude-3-5-sonnet-20241022
   ```

2. **(Optional) Use Ollama locally**:
   ```bash
   # Install Ollama from https://ollama.ai
   ollama pull llama2:7b
   ```

### Usage

```python
from agents.examples import CodeAnalysisAgent
from config.parser import ConfigParser

# Load configuration
ConfigParser.load()

# Create agent (loads config from config.ini automatically)
agent = CodeAnalysisAgent()

# Execute with code to analyze
result = await agent.execute(
    code="""
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
""",
    user_input="Analyze this code"
)

# Access results
print(result["code_analysis"])
print(agent.state.to_dict())
```

## Configuration

### config.ini Structure

Configuration is loaded from `config.ini` using the `SubSectionParser` pattern:

```ini
[ollama]
base_url = http://localhost:11434
model = llama2:7b
temperature = 0.7
max_tokens = 4096
timeout = 60
keep_alive = 5m

[openai]
api_key = your-api-key
model = gpt-4
temperature = 0.7
max_tokens = 4096
timeout = 60
organization_id =

[anthropic]
api_key = your-api-key
model = claude-3-5-sonnet-20241022
temperature = 0.7
max_tokens = 4096
timeout = 60
```

### Loading Configuration

```python
from config.parser import ConfigParser
from config.providers import OllamaConfig

# Load configuration (auto-loads from project root config.ini)
ConfigParser.load()

# Get provider config
ollama_config = ConfigParser.get(OllamaConfig)
print(ollama_config.model)  # llama2:7b
```

## Development

### Code Quality

```bash
# Format code
black agents/ providers/ config/ tests/

# Lint
ruff check agents/ providers/ config/ tests/

# Type check
mypy agents/ providers/ config/ tests/

# All checks
black agents/ providers/ config/ tests/ && \
  ruff check agents/ providers/ config/ tests/ && \
  mypy agents/ providers/ config/ tests/
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_base_agent.py::TestAgentCreation -v

# With coverage
pytest tests/ --cov=agents --cov=providers --cov=config

# Watch mode (requires pytest-watch)
ptw tests/
```

## Extending the System

### Creating a Custom Agent

Agents use a **declarative pattern** with class attributes:

```python
from agents.base import BaseAgent
from langchain_core.tools import tool

# Define tools
@tool
async def analyze_complexity(code: str) -> str:
    """Analyze code complexity."""
    return f"Complexity analysis for {len(code)} chars"

# Define agent
class MyAnalysisAgent(BaseAgent):
    prompt = """You are an expert code analyzer.

    Analyze code structure and complexity."""

    tools = [analyze_complexity]

    return_state_field = "my_analysis"

    # Optional overrides
    max_iterations = 8
    temperature = 0.3
    provider_name = "anthropic"

# Use the agent
agent = MyAnalysisAgent()
result = await agent.execute(code="...", user_input="Analyze this")
print(result["my_analysis"])
```

**Key Agent Attributes:**
- `prompt` - System prompt (required, non-empty string)
- `tools` - List of tools available to agent (required, list of callables)
- `return_state_field` - State field to store results (required, valid Python identifier)
- `max_iterations` - Max agentic loop iterations (default: 10)
- `temperature` - LLM temperature (default: 0.7)
- `provider_name` - Which provider to use (default: "ollama")

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
    timeout: int = 60

# 2. Implement provider
class CustomProvider(BaseProvider):
    def __init__(self, config: CustomConfig):
        self.config = config

    async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> ProviderResponse:
        # Call your API
        response = await self._call_api(system_prompt, user_prompt)

        return ProviderResponse(
            content=response["output"],
            model=self.config.model,
            usage={"tokens": response.get("tokens", 0)}
        )

    async def validate_connection(self) -> bool:
        # Test connection
        try:
            # Test call
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
│         Optimized Code + Report             │
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
is_valid = await ProviderRegistry.validate_provider("openai")

# List available
available = ProviderRegistry.get_available()
```

### Configuration Pattern
Dataclass-based configuration with INI mapping:
```python
from config.parser import ConfigParser
from config.providers import OllamaConfig

ConfigParser.load()
config = ConfigParser.get(OllamaConfig)
```

### Agentic Loop
Continuous refinement pattern: Think → Tool Use → Observe
```
1. Think: LLM processes context with available tools
2. Tool Use: LLM calls tools in JSON format
3. Observe: Tool results fed back to LLM
4. Repeat: Until task_complete or max_iterations
```

### State Management
Agent state is LangGraph-compatible:
```python
@dataclass
class AgentState:
    messages: list           # Conversation history
    tool_results: list      # Tool execution results
    final_result: str       # Agent output
    iteration_count: int    # Loop iterations
    status: AgentStatus     # IDLE, THINKING, USING_TOOL, etc.
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
- **Retry Logic**: Built-in retry mechanism for failed API calls

## Security & Privacy

- **Local Processing**: Use Ollama for complete local code analysis without sending data to external services
- **Provider Abstraction**: Easily switch providers based on your security requirements
- **No Code Storage**: By default, code is not persisted unless explicitly configured
- **Input Validation**: All inputs are validated before processing

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

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Status & Next Steps

**Currently Implemented:**
- ✅ Agent framework with declarative pattern
- ✅ Provider abstraction (Ollama, OpenAI, Anthropic)
- ✅ Configuration system (INI-based)
- ✅ Agentic loop implementation
- ✅ Tool binding and execution

**Next Implementation Phase:**
- [ ] Specialized agents (Environment, Behavior, Component Summary)
- [ ] Code analysis tools
- [ ] Repository storage system
- [ ] LangGraph workflow integration
- [ ] Comprehensive test suite
- [ ] Documentation and examples

## Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- LLM providers: [Ollama](https://ollama.ai), [OpenAI](https://openai.com), [Anthropic](https://anthropic.com)
