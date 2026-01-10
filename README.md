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
├── .gitignore
├── README.md
├── requirements.txt
├── pyproject.toml
│
├── src/agentic_optimizer/
│   ├── core/                    # Base classes & state management
│   ├── providers/               # LLM provider implementations
│   ├── repository/              # Code storage and retrieval
│   ├── agents/                  # Agent implementations
│   ├── workflows/               # LangGraph workflows
│   ├── prompts/                 # Agent prompts
│   └── utils/                   # Utilities and helpers
│
├── tests/                       # Unit and integration tests
├── examples/                    # Usage examples
└── config/                      # Configuration files
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

1. **Configure Ollama** (default provider):
   ```bash
   # Install Ollama from https://ollama.ai
   # Run Ollama and pull a model:
   ollama pull llama2:7b
   ```

2. **Create .env file**:
   ```bash
   cp .env.example .env
   ```

3. **Edit .env** for your settings:
   ```env
   DEFAULT_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=llama2:7b
   ```

### Usage

```python
from agentic_optimizer import OptimizationOrchestrator
from agentic_optimizer.providers import ProviderFactory, LLMConfig

# Create provider (Ollama, OpenAI, or Anthropic)
config = LLMConfig(model_name="llama2:7b", temperature=0.7)
provider = ProviderFactory.create("ollama", config)

# Initialize orchestrator
orchestrator = OptimizationOrchestrator(provider)

# Optimize code
result = await orchestrator.optimize(
    source_code="""
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
""",
    language="python",
    optimization_types=["performance", "quality"]
)

print(result.optimized_code)
print(result.optimization_suggestions)
```

## Configuration

### Environment Variables (.env)

```env
# Provider Selection
DEFAULT_PROVIDER=ollama              # ollama, openai, anthropic
FALLBACK_PROVIDER=openai             # Fallback if primary fails

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2:7b
OLLAMA_TIMEOUT=300

# OpenAI Configuration (optional)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4

# Anthropic Configuration (optional)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# General Settings
LOG_LEVEL=INFO
MAX_RETRIES=3
TIMEOUT=300
```

## Development

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src/agentic_optimizer
```

### Code Formatting & Linting

```bash
# Format code
black src/ tests/

# Check code quality
ruff check src/ tests/

# Type checking
mypy src/
```

## Extending the System

### Adding a Custom Agent

```python
from agentic_optimizer.core import BaseAgent, AgentContext

class CustomAnalysisAgent(BaseAgent):
    def get_agent_name(self) -> str:
        return "custom_analysis_agent"

    def validate_input(self, context: AgentContext) -> bool:
        return context.state.get("source_code") is not None

    async def execute(self, context: AgentContext) -> dict:
        code = context.state["source_code"]
        # Your analysis logic here
        return {
            "custom_analysis": "Your analysis results"
        }
```

### Adding a Custom Provider

```python
from agentic_optimizer.providers import BaseLLMProvider, ProviderFactory, LLMConfig

class CustomProvider(BaseLLMProvider):
    async def generate(self, system_prompt: str, user_prompt: str, **kwargs):
        # Your implementation
        pass

    async def validate_connection(self) -> bool:
        # Check connection
        return True

    def get_provider_name(self) -> str:
        return "custom_provider"

# Register the provider
ProviderFactory.register_provider("custom", CustomProvider)
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

### Provider Factory Pattern
Seamlessly switch between LLM providers without changing agent code:
```python
# Switch providers at runtime
provider = ProviderFactory.create("ollama", config)   # Local
provider = ProviderFactory.create("openai", config)   # Cloud
provider = ProviderFactory.create("anthropic", config) # Claude
```

### Agent Base Class
All agents inherit from `BaseAgent` with consistent interface:
- `execute(context)` - Main agent logic
- `validate_input(context)` - Input validation
- `get_agent_name()` - Unique identifier
- Automatic metrics collection

### State Management
LangGraph state flows through the workflow:
```python
OptimizationState = {
    "source_code": str,
    "language": str,
    "environment_summary": str,
    "behavior_summary": str,
    "component_summary": str,
    "analysis_results": dict,
    "optimized_code": str,
    "optimization_suggestions": list
}
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

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing documentation
- Review examples in the `examples/` directory

## Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- LLM providers: [Ollama](https://ollama.ai), [OpenAI](https://openai.com), [Anthropic](https://anthropic.com)
