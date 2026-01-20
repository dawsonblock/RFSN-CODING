<div align="center">

# 🤖 RFSN Controller

### Autonomous AI Code Repair & Feature Generation

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

**RFSN** (Robotic Fix & Synthesis Network) is an autonomous coding agent that can analyze repositories, identify bugs, generate patches, and implement features—all within a secure sandbox environment.

[Features](#-features) • [Quick Start](#-quick-start) • [Usage](#-usage) • [Architecture](#-architecture) • [Performance](#-performance)

</div>

---

## ✨ Features

<tr>
<td width="50%">

### 🔧 **Autonomous Repair**

- Analyzes failing tests
- Generates minimal patches
- Validates before committing
- Multi-temperature sampling

</td>
<td width="50%">

### 🚀 **Feature Generation**

- Implements from description
- Creates tests & documentation
- Follows project conventions
- Incremental subgoal completion

</td>
</tr>
<tr>
<td>

### 🧠 **Self-Learning**

- **Action-Outcome Memory**: Remembers past successes/failures.
- **Context Persistence**: Never forgets read files.
- **Optimized Strategy**: Prioritizes proven tools over time.

</td>
<td>

### 📊 **Real-Time Dashboard**

- Live step-by-step visualization.
- Secure API key management.
- Performance metrics & cost tracking.
- Modern dark-mode UI.

</td>
</tr>
<tr>
<td>

### 🛡️ **Zero-Trust Security**

- **Fail-Closed Verification**: Aborts on any violation.
- **APT Injection Guard**: Blocks malicious package names.
- **Deterministic Signatures**: Prevents tool tampering.
- **Path Jail**: strict `../` blocking.

</td>
<td>

### ⚡ **Optimized Performance**

- **3x Faster**: Parallel LLM patch generation.
- **10x Faster**: Smart file cache & incremental tests.
- **<1s Cold Start**: Docker pre-warming.
- **Async Streaming**: Instant token feedback.

</td>
</tr>
</table>

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/dawsonblock/RFSN-CODING.git
cd RFSN-CODING

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### Set API Key

```bash
export DEEPSEEK_API_KEY="your-api-key"
```

### 📊 Launch Dashboard (Optional)

```bash
# Start the real-time UI
uvicorn rfsn_dashboard.main:app --host 127.0.0.1 --port 8000 &
# Open http://localhost:8000
```

### Run Your First Repair

```bash
# Fix failing tests in a repository
rfsn --repo https://github.com/owner/repo --test "pytest -q"
```

---

## 📖 Usage

### Basic Commands

```bash
# Repair mode (fix failing tests)
rfsn --repo https://github.com/owner/repo

# Feature mode (implement new features)
rfsn --repo URL --feature-mode --feature-description "Add user authentication"

# With custom test command
rfsn --repo URL --test "npm test"

# Limit iterations
rfsn --repo URL --steps 10
```

### Performance Flags

```bash
# Maximum speed (3x + 10x speedup)
rfsn --repo URL --parallel-patches --incremental-tests --enable-llm-cache

# Multi-model ensemble (higher success rate)
rfsn --repo URL --ensemble-mode

# With monitoring
rfsn --repo URL --enable-telemetry --telemetry-port 9090
```

### All Options

| Flag | Description |
|------|-------------|
| `--repo URL` | Repository to analyze (required) |
| `--test CMD` | Test command (default: auto-detect) |
| `--steps N` | Maximum iterations (default: 12) |
| `--feature-mode` | Enable feature generation |
| `--feature-description` | Feature to implement |
| `--parallel-patches` | Generate 3 patches in parallel |
| `--incremental-tests` | Run only affected tests first |
| `--enable-llm-cache` | Cache LLM responses |
| `--ensemble-mode` | Use multiple LLM models |
| `--enable-telemetry` | Enable metrics & tracing |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     RFSN Controller                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐│
│  │  CLI    │→ │ Config  │→ │ Sandbox │→ │ Docker Container││
│  └─────────┘  └─────────┘  └─────────┘  └─────────────────┘│
│       ↓                         ↑                           │
│  ┌─────────┐  ┌─────────┐  ┌───┴─────┐  ┌─────────────────┐│
│  │   LLM   │← │ Prompts │← │Verifier │← │  Test Results   ││
│  │ (async) │  └─────────┘  └─────────┘  └─────────────────┘│
│  └─────────┘                                               │
│       ↓                                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                     │
│  │ Patches │→ │ Hygiene │→ │ Apply   │→ ✅ Success         │
│  └─────────┘  └─────────┘  └─────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `controller.py` | Main orchestration loop |
| `sandbox.py` | Isolated execution environment |
| `llm_deepseek.py` | LLM API client with retry |
| `llm_async.py` | Async calls, caching, streaming |
| `llm_ensemble.py` | Multi-model scoring |
| `parallel.py` | Concurrent patch evaluation |
| `verifier.py` | Test execution & validation |
| `telemetry.py` | OpenTelemetry + Prometheus |

---

## ⚡ Performance

### Optimization Modules

| Module | Feature | Impact |
|--------|---------|--------|
| `performance.py` | Docker pre-warming | **30-60x** faster cold start |
| `performance.py` | Worktree pooling | **2x** faster parallel eval |
| `llm_async.py` | Parallel generation | **3x** faster patches |
| `llm_async.py` | Response caching | **90%** cost reduction |
| `incremental_testing.py` | Smart test selection | **10x** faster feedback |
| `optimizations.py` | Lazy loading | **2x** faster startup |
| `smart_file_cache.py` | LRU file cache | **10x** faster reads |

### Benchmarks

```
┌────────────────────┬──────────┬──────────┬─────────────┐
│ Operation          │ Before   │ After    │ Improvement │
├────────────────────┼──────────┼──────────┼─────────────┤
│ Docker cold start  │ 30-60s   │ <1s      │ 30-60x      │
│ LLM calls (3 temp) │ ~9s      │ ~3s      │ 3x          │
│ Test runs (large)  │ 60s      │ 6s       │ 10x         │
│ File reads         │ 10ms     │ 1ms      │ 10x         │
│ CLI startup        │ 5s       │ 2s       │ 2.5x        │
└────────────────────┴──────────┴──────────┴─────────────┘
```

### 🏆 Case Study: Quicksort Solved

The controller autonomously diagnosed and fixed a complex recursion bug in `QuixBugs/quicksort`.

- **Bug**: Missing duplicates (`x > pivot` vs `x >= pivot`).
- **Diagnosis**: Model read test data, identified dropped elements, and traced logic.
- **Solution**: Patched the list comprehension in 4 steps.
- **Key Enabler**: Context persistence and Action-Outcome Learning prevented infinite loops.

---

## 📊 Observability

Enable full observability with OpenTelemetry and Prometheus:

```bash
rfsn --repo URL --enable-telemetry --telemetry-port 9090
```

### Metrics Exposed

- `rfsn_patches_evaluated_total` - Patch success/fail counts
- `rfsn_llm_calls_total` - LLM API call metrics
- `rfsn_llm_tokens_total` - Token usage tracking
- `rfsn_llm_latency_seconds` - API latency histogram
- `rfsn_test_duration_seconds` - Test execution time

---

## 🔒 Security

RFSN includes multiple security layers:

- **Command Allowlist** - Only approved commands execute
- **Docker Isolation** - All code runs in containers
- **Escape Detection** - Blocks breakout attempts
- **Credential Stripping** - API keys never leak to sandbox
- **Patch Hygiene** - Validates patch size and scope

---

## 🛠️ Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run lints
make lint

# Run tests
make test

# Format code
make format
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ for autonomous coding**

[Report Bug](https://github.com/dawsonblock/RFSN-CODING/issues) • [Request Feature](https://github.com/dawsonblock/RFSN-CODING/issues)

</div>
