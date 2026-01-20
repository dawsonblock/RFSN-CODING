# RFSN Sandbox Controller – Production-Ready Upgrade

## What Changed

This release contains a number of critical security and packaging improvements to turn the
RFSN Sandbox Controller into a production‑ready tool while preserving its strict safety
model and self‑improvement capabilities.

### Security Hardening

- **Docker command sanitization** – `docker_run` now calls
  `is_command_allowed()` on every command before execution. Commands
  containing shell metacharacters or blocked patterns are rejected up front.
- **Environment scrubbing** – All subprocess and Docker invocations now remove
  sensitive API keys (`DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`,
  `ANTHROPIC_API_KEY`) from the environment to prevent accidental leakage to
  child processes.
- **Resource limits** – Docker invocations are constrained with CPU, memory
  and PID limits and now include a `--storage-opt size=10G` flag to prevent
  disk exhaustion attacks inside containers.
- **Immutable control surface** – A new `IMMUTABLE_CONTROL_PATHS` constant in
  `patch_hygiene.py` enumerates core files that must never be modified by
  automated patches. `validate_patch_hygiene()` now rejects diffs that touch
  these files.
- **Command allowlist tightened** – `make` has been removed from the
  allowlist due to its ability to run arbitrary shell commands via Makefiles.

### Packaging & Hygiene

- **Duplicate repos removed** – Nested copies (`rfsn_sandbox/`, `Uploads/`)
  and run artifacts (`results/`) are no longer included in the shipping
  archive.
- **Cache and bytecode removal** – `__pycache__`, `.pytest_cache`, and
  `.pyc` files are purged from the final distribution to reduce size and
  prevent hidden bytecode injection.
- **QuixBugs tests gated** – Top‑level `test_quixbugs.py` and
  `test_quixbugs_direct.py` have been moved under
  `tests/integration/` with a `@pytest.mark.integration` marker and
  network gating via `_netgate.require_network()`. They no longer insert
  hardcoded local paths.
- **Release sanity tests** – Added `tests/unit/test_release_sanity.py` to
  assert that no duplicate repos, caches, or absolute developer paths are
  present and that the immutable control surface is enforced.
- **Optional LLM dependencies** – Heavy model SDKs (`openai`, `google‑genai`)
  have been split into `requirements-llm.txt`. The core `requirements.txt`
  now lists only minimal runtime dependencies (`python-dotenv`). LLM client
  modules raise a clear error instructing users to install the extras if
  missing.
- **Documentation updates** – The README has been updated with new
  installation instructions (optional LLM extras), an explanation of
  learning modes (`observe`, `active`, `locked`), and guidance on promotion
  gating for self‑improvement.