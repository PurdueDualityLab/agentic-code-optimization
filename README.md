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
git clone https://github.com/PurdueDualityLab/agentic-code-optimization.git
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
# Run any Agent on current directory
python evaluate.py EnvironmentSummarizer /path/to/repo

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
git submodule update --init --recursive
```

**3. Run Optimization:**
```bash
# Activate virtual environment
source .env

# Run optimization pipeline on TeaStore
 python evaluate.py orchestrate_complete_pipeline TeaStore

# Review generated optimizations in:
# - runs/<timestamp>/response.txt
# - TeaStore source files (modified in place)
```

**4. Apply Optimizations & Test:**
```bash
# Rebuild with optimizations
cd TeaStore
./build_docker.sh -r master-teastore

# Start Services
docker compose -f ./examples/docker/docker-compose_default.yaml up -d

# Run optimized test
jmeter -n -t examples/jmeter/teastore_browse_nogui.jmx -Jhostname localhost -Jport 8080 -JnumUser 10 -JrampUp 1 -l mylogfile.log

# Compare results:
# baseline vs optimized metrics
# In Root Repo
python analyze_jmeter_logs.py
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


## Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- Providers: [OpenAI](https://openai.com), [Anthropic](https://anthropic.com), [Gemini](https://ai.google.dev/), [Ollama](https://ollama.ai)
- Static Analysis: [CodeQL](https://codeql.github.com/)
- Benchmark: [TeaStore](https://github.com/DescartesResearch/TeaStore)
