<div align="center">

# 🤖 RFSN Controller

### Autonomous AI Code Repair & Feature Generation

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776ab?logo=python&logoColor=white)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-316%20passed-brightgreen)](tests/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)

**RFSN** is an autonomous coding agent that analyzes repositories, identifies bugs, generates patches, and implements features—all within a secure sandbox.

[Quick Start](#-quick-start) • [Features](#-features) • [Usage](#-usage) • [Architecture](#-architecture)

</div>

---

## 🚀 Quick Start

```bash
# Clone & install
git clone https://github.com/dawsonblock/RFSN-CODING.git
cd RFSN-CODING && uv sync

# Set API key
export DEEPSEEK_API_KEY="your-key"

# Fix bugs in any repo
rfsn --repo https://github.com/owner/repo --test "pytest -q"
```

**Optional: Launch Dashboard**

```bash
uvicorn rfsn_dashboard.main:app --port 8000 &
# → http://localhost:8000
```

---

## ✨ Features

| | |
|:---:|:---:|
| 🔧 **Autonomous Repair** | 🚀 **Feature Generation** |
| Analyzes failing tests, generates minimal patches, validates before committing | Implements from description, creates tests & docs, follows conventions |
| 🧠 **Self-Learning** | 📊 **Real-Time Dashboard** |
| Action-outcome memory, context persistence, optimized tool selection | Live visualization, cost tracking, dark-mode UI |
| 🛡️ **Zero-Trust Security** | ⚡ **Optimized Performance** |
| Fail-closed verification, APT injection guard, path jail | 3x faster LLM calls, 10x faster tests, <1s cold start |

---

## 📖 Usage

### Repair Mode

```bash
rfsn --repo https://github.com/owner/repo
```

### Feature Mode

```bash
rfsn --repo URL --feature-mode --feature-description "Add user authentication"
```

### Elite Mode (DAG Planner + Thompson Sampling)

```bash
rfsn --repo URL \
  --planner-mode dag \
  --policy-mode bandit \
  --learning-db ./learning.db \
  --repo-index
```

### Performance Flags

```bash
rfsn --repo URL \
  --parallel-patches \
  --incremental-tests \
  --enable-llm-cache \
  --ensemble-mode
```

### Key Options

| Flag | Description |
|------|-------------|
| `--repo URL` | Repository to analyze **(required)** |
| `--test CMD` | Test command (default: auto-detect) |
| `--steps N` | Max iterations (default: 12) |
| `--feature-mode` | Enable feature generation |
| `--planner-mode dag` | DAG-based multi-step execution |
| `--policy-mode bandit` | Thompson Sampling action selection |
| `--parallel-patches` | Generate 3 patches in parallel |
| `--enable-llm-cache` | Cache LLM responses |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     RFSN Controller                         │
├─────────────────────────────────────────────────────────────┤
│  CLI → Config → Sandbox → Docker Container                  │
│   ↓                          ↑                              │
│  LLM ← Prompts ← Verifier ← Test Results                    │
│   ↓                                                         │
│  Patches → Hygiene → Apply → ✅ Success                     │
└─────────────────────────────────────────────────────────────┘
```

### Core Modules

| Module | Purpose |
|--------|---------|
| `controller.py` | Main orchestration loop |
| `sandbox.py` | Isolated Docker execution |
| `planner.py` | DAG-based planning |
| `policy_bandit.py` | Thompson Sampling learning |
| `eval_harness.py` | Evaluation metrics |
| `exec_utils.py` | Secure command execution |

---

## ⚡ Performance

| Operation | Before | After | Improvement |
|-----------|--------|-------|-------------|
| Docker cold start | 30-60s | <1s | **30-60x** |
| LLM calls (3 temps) | ~9s | ~3s | **3x** |
| Test runs (large) | 60s | 6s | **10x** |
| File reads | 10ms | 1ms | **10x** |

---

## 🔒 Security

- **Command Allowlist** – Only approved commands execute
- **Docker Isolation** – All code runs in containers
- **Shell=False Enforcement** – No shell injection possible
- **Path Jail** – Blocks directory traversal
- **Patch Hygiene** – Validates patch size and scope

See [SECURITY.md](SECURITY.md) for details.

---

## 🛠️ Development

```bash
uv sync --all-extras    # Install dev deps
make lint               # Run lints
make test               # Run 316 tests
```

---

## 📄 License

MIT License – see [LICENSE](LICENSE)

---

<div align="center">

**Built with ❤️ for autonomous coding**

[Report Bug](https://github.com/dawsonblock/RFSN-CODING/issues) • [Request Feature](https://github.com/dawsonblock/RFSN-CODING/issues)

</div>
