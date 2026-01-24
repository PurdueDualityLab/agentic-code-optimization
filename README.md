# Agentic Code Optimizer

Multi-agent framework for system-level software optimization using LLMs and static analysis. Built with LangGraph for coordinated agent workflows.

## Architecture

**5-Phase Pipeline:**

```
Input Code
    ↓
PHASE 1: SUMMARIZATION (Parallel)
├─ Environment Summary Agent  → Dependencies, imports, build config
├─ Behavior Summary Agent     → Control flow, call graphs, sync patterns
└─ Component Summary Agent    → Structure, interfaces, dependencies
    ↓
PHASE 2: STATIC ANALYSIS
└─ CodeQL Analysis → Hotspots, patterns, architectural signals
    ↓
PHASE 3: ANALYSIS
└─ Analyzer Agent → Identifies optimization opportunities
    ↓
PHASE 4: OPTIMIZATION
└─ Optimization Agent → Generates code changes
    ↓
PHASE 5: VERIFICATION
└─ Code Correctness Agent → Validates functional equivalence
```

**Key Features:**
- **Multi-agent coordination** via LangGraph workflows
- **Static analysis integration** with CodeQL
- **Provider-agnostic** (OpenAI, Anthropic, Gemini, Ollama/local)
- **System-level reasoning** across components and services
- **Artifact tracking** with comprehensive run management

## Requirements

- **Python 3.11+** (required for `tomllib`)
- **CodeQL CLI** (for static analysis): https://github.com/github/codeql-cli-binaries
- **Apache JMeter** (for benchmarking): https://jmeter.apache.org

## Installation

```bash
# Clone repository
git clone <repository-url>
cd agentic-code-optimization

# Create virtual environment (Python 3.11+ required)
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your API keys
```

### Configure API Keys

Edit `.env`:
```bash
# Choose your provider(s)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...

# Or use Ollama locally (no API key needed)
OLLAMA_BASE_URL=http://localhost:11434
```

Edit `config.ini`:
```ini
[agents]
default_provider = anthropic  # or openai, gemini, ollama
temperature = 0.7
max_iterations = 30

[anthropic]
api_key = ${ANTHROPIC_API_KEY}
model = claude-3-5-sonnet-20241022

[openai]
api_key = ${OPENAI_API_KEY}
model = gpt-4

[ollama]
base_url = http://localhost:11434
model = codellama:latest
```

## Running the Pipeline

### Basic Usage

```bash
# Run optimization on current directory
python evaluate.py

# Run on specific repository
python evaluate.py /path/to/repo

# Full pipeline with correctness verification
python evaluate_code_correctness.py /path/to/repo
```

### Output

Results are saved to `runs/<AgentName>_<timestamp>/`:
```
runs/EnvironmentSummarizer_20250124_120000/
├── config.ini       # Configuration snapshot
├── input.txt        # Execution parameters
├── response.txt     # Agent output
├── metrics.json     # LLM calls, tools used, timing
├── state.json       # Agent state snapshot
└── summary.md       # Human-readable summary
```

## Running Benchmarks

### TeaStore Microservices Benchmark

**1. Setup TeaStore:**
```bash
# Clone TeaStore (if not already in repo)
git clone https://github.com/DescartesResearch/TeaStore.git
cd TeaStore

# Build (requires Java 11+, Maven, Docker)
./build.sh

# Start services
docker-compose up -d
```

**2. Baseline Performance Test:**
```bash
# Install JMeter: https://jmeter.apache.org/download_jmeter.cgi

# Run baseline test (master branch)
jmeter -n -t TeaStore/examples/jmeter/teastore_browse.jmx \
  -l results_baseline.jtl \
  -e -o reports/baseline/

# Record metrics:
# - Throughput (req/sec)
# - Average response time (ms)
# - P50, P90, P99 latencies (ms)
# - Error rate (%)
```

**3. Run Optimization:**
```bash
# Activate virtual environment
source venv/bin/activate

# Run optimization pipeline on TeaStore
python evaluate_code_correctness.py TeaStore/

# Review generated optimizations in:
# - runs/<timestamp>/response.txt
# - TeaStore source files (modified in place)
```

**4. Apply Optimizations & Test:**
```bash
# Rebuild with optimizations
cd TeaStore
./build.sh

# Restart services
docker-compose down
docker-compose up -d

# Run optimized test
jmeter -n -t examples/jmeter/teastore_browse.jmx \
  -l results_optimized.jtl \
  -e -o reports/optimized/

# Compare results:
# baseline vs optimized metrics
```

**5. Compare Performance:**
```bash
# JMeter generates HTML reports in:
# - reports/baseline/index.html
# - reports/optimized/index.html

# Key metrics to compare:
# - Throughput improvement (%)
# - Response time reduction (%)
# - Latency percentiles (P50, P90, P99)
# - Error rate changes
```

### Example Results

From our TeaStore evaluation:
- **Throughput**: +36.58% (1197.79 → 1635.89 req/sec)
- **Avg Response Time**: -27.81% (12.84 → 9.27 ms)
- **P50 Latency**: -30.77% (13.00 → 9.00 ms)
- **Error Rate**: -100% (0.0048% → 0.00%)

**Key Optimizations Identified:**
1. HTTP client reuse via singleton pattern
2. Lock contention removal (synchronized → volatile)
3. ObjectMapper instance sharing

## Project Structure

```
agentic-code-optimization/
├── agents/                    # Agent framework
│   ├── base.py               # BaseAgent with LangGraph
│   ├── summarizers/          # Phase 1: Parallel summarization
│   │   ├── environment.py
│   │   ├── behavior.py
│   │   └── component.py
│   ├── analyzers/            # Phase 3: Analysis
│   └── checkers/             # Phase 5: Verification
├── providers/                # LLM provider abstraction
│   ├── base.py
│   ├── registry.py
│   ├── openai.py
│   ├── anthropic.py
│   └── ollama.py
├── tools/                    # Code analysis tools
├── utils/                    # Metrics & run management
├── config/                   # Configuration system
├── evaluate.py               # Main execution script
├── evaluate_code_correctness.py  # Full pipeline
├── config.ini                # Provider configuration
└── requirements.txt          # Python dependencies
```

## Development

### Code Quality

```bash
# Format
black agents/ config/ providers/ tools/ utils/ evaluate.py

# Lint
ruff check agents/ config/ providers/ tools/ utils/ evaluate.py

# Type check
mypy agents/ config/ providers/ tools/ utils/ evaluate.py

# All checks
black . && ruff check . && mypy .
```

### Testing

```bash
pytest tests/ --cov=agents --cov=providers --cov=config
```

## Creating Custom Agents

```python
from agents.base import BaseAgent
from langchain_core.tools import tool

@tool
def analyze_code(code: str) -> str:
    """Analyze code structure."""
    return "analysis result"

class MyAgent(BaseAgent):
    prompt = """You are a code analysis expert..."""
    tools = [analyze_code]
    return_state_field = "analysis_result"
    max_iterations = 8
    temperature = 0.3
    provider_name = "anthropic"

# Use
agent = MyAgent()
result = agent.run("/path/to/code")
print(f"LLM calls: {agent.iteration_count}")
```

## License

MIT License - see LICENSE file for details.

## Citation

```bibtex
@inproceedings{peng2026agentic,
  title={Beyond Local Code Optimization: Multi-Agent Reasoning for Software System Optimization},
  author={Peng, Huiyun and Zhong, Antonio Qiu and Patil, Parth Vinod and Thiruvathukal, George K. and Davis, James C.},
  booktitle={Conference Proceedings},
  year={2026}
}
```

## Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- Providers: [OpenAI](https://openai.com), [Anthropic](https://anthropic.com), [Gemini](https://ai.google.dev/), [Ollama](https://ollama.ai)
- Static Analysis: [CodeQL](https://codeql.github.com/)
- Benchmark: [TeaStore](https://github.com/DescartesResearch/TeaStore)
