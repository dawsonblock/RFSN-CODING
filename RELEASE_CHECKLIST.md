# Release Checklist – RFSN Sandbox Controller

This document outlines the steps required to prepare, test and package the
RFSN Sandbox Controller for production distribution.

## Preparation

1. Create a clean working directory for the build.
2. Ensure Python 3.9 or higher is available on your system.

## Installation

1. Create a virtual environment and activate it:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use .venv\Scripts\activate
   ```

2. Install the core dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. *(Optional)* Install LLM backends if you intend to use hosted models (OpenAI, DeepSeek, Gemini):

   ```bash
   pip install -r requirements-llm.txt
   ```

4. Copy the environment template and set any required API keys:

   ```bash
   cp .env.example .env
   # Edit .env and add DEEPSEEK_API_KEY, GEMINI_API_KEY or other keys if using those providers
   ```

## Testing

Run the full unit test suite to ensure core functionality and safety gates are intact:

```bash
pytest -q
```

Integration tests (e.g. QuixBugs) require network access and are skipped by default.
To run them, set an environment variable and allow network access:

```bash
export RUN_INTEGRATION=1
pytest -m integration -q
```

All tests should pass before packaging.

## Packaging

1. Remove development artifacts from the repository:
   - Delete any `__pycache__` and `.pytest_cache` directories.
   - Delete any `*.pyc` files.
   - Ensure that no `results/`, `rfsn_sandbox/` or `Uploads/` directories remain.

2. Create the distribution archive from the cleaned root:

   ```bash
   zip -r RFSN-SANDBOX-SHIP_CLEAN.zip \
       rfsn_controller \
       tests \
       Dockerfile docker-compose.yml pytest.ini \
       requirements.txt requirements-llm.txt \
       README.md FEATURE_MODE.md CHANGELOG.md RELEASE_CHECKLIST.md
   ```

3. Verify that the zip does **not** include compiled bytecode or caches and contains only the necessary files.

## Validation

After creating the zip, perform these checks in a temporary directory:

1. Unzip the archive.
2. Run Python’s bytecode compilation to detect syntax errors:

   ```bash
   python -m compileall -q rfsn_controller tests
   ```

3. Run the unit tests again inside the unzipped directory to ensure nothing was lost in packaging.

4. Search for absolute local paths (e.g. `home/username`) and ensure none are present in any code or docs.

## Self‑Improvement Guidance

The controller’s learning layer can reorder allowed tool requests and choose prompt
templates based on past outcomes. Use the `--learning-mode` flag to control this:

- `observe`: Collects priors but makes no behavioural changes. Use this for initial runs and benchmarking.
- `active`: Reorders tool requests and selects prompt recipes based on priors. Enable only after thorough evaluation in observe mode.
- `locked`: Disables learning entirely.

When enabling learning, specify a database file path with `--learning-db`:

```bash
python -m rfsn_controller.cli \
  --repo "https://github.com/OWNER/REPO" \
  --learning-mode observe \
  --learning-db ./rfsn_learning.sqlite \
  --steps 12
```

Promote to `active` mode only after confirming that observe mode yields consistent improvements
with no regressions on a representative set of repositories.