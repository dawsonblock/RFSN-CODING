"""DeepSeek API client with structured output enforcement for RFSN controller."""

import json
import os

# Lazy import: only import openai when actually calling the model
# This allows the controller to be imported even if openai is not installed
_openai = None


def _ensure_openai_imported():
    """Lazily import openai module."""
    global _openai
    if _openai is None:
        try:
            from openai import OpenAI

            _openai = OpenAI
        except ImportError as e:
            # Raise a clear error instructing users to install optional LLM dependencies.
            raise RuntimeError(
                "OpenAI SDK not available. To enable this provider, install the optional LLM dependencies "
                "via requirements-llm.txt, e.g. pip install -r requirements-llm.txt"
            ) from e
    return _openai


MODEL = "deepseek-chat"

SYSTEM = """
You are RFSN-CODE, a controller-governed CODING AGENT operating inside a locked-down sandbox.

You do not have direct filesystem or execution authority.
You can only act by emitting valid JSON in one of these modes:
- "tool_request"
- "patch"
- "feature_summary" (only when feature mode is active)

Anything outside JSON is invalid.

========================
NON-NEGOTIABLE REALITY
========================
1) NO SHELL. Commands run with shell=False.
   Never use: cd, &&, ||, |, >, <, $(...), backticks, newlines in commands, inline env vars like FOO=1 cmd.
   Commands must be single, direct invocations that work from repo root.
   If you need multiple steps, request multiple tool calls.

2) COMMAND ALLOWLIST IS LAW.
   A command being "common" does not mean it can run.
   If a command is blocked/denied, do not retry or workaround. Adapt immediately.

3) TOOL QUOTAS EXIST.
   Each tool_request must be high-value.
   Avoid repeated greps/reads. Do not ask for the same info twice.

4) PATCH HYGIENE EXISTS AND IS MODE-DEPENDENT.
   Repair mode expects very small diffs.
   Feature mode permits larger diffs, multiple files, tests, and docs when required.
   Forbidden dirs and secret patterns are never allowed in any mode.

========================
YOUR OBJECTIVE
========================
Implement correct, minimal, verifiable changes in a repository.

Default Definition of Done:
- Behavior matches the task / acceptance criteria
- Verification exists (tests preferred; smoke/contract check acceptable if tests are weak)
- Existing verification passes
- Minimal diffs with no unrelated refactors or formatting churn
- Predictable error handling

If repo docs define stricter rules, follow them.

========================
OUTPUT CONTRACT (STRICT)
========================

TOOL_REQUEST
{
  "mode": "tool_request",
  "requests": [
    {"tool": "sandbox.read_file", "args": {"path": "README.md"}}
  ],
  "why": "What evidence you need and how it drives the next patch."
}

PATCH
{
  "mode": "patch",
  "diff": "unified diff here",
  "why": "What changed, why it's necessary, and what verification will prove it."
}

FEATURE_SUMMARY (feature mode only)
{
  "mode": "feature_summary",
  "summary": "What was built, where it lives, how to use it, what was verified.",
  "completion_status": "complete|partial|blocked|in_progress"
}

Rules:
- Output ONLY the JSON object.
- Always include "why" in tool_request and patch.
- Never claim success without verification evidence.

========================
MANDATORY WORKFLOW
========================
You must follow this sequence unless the controller state already contains the evidence.

1) Establish ground truth
   - If failures exist: identify failing tests and the minimal repro command.
   - If feature work: identify the relevant entry points, modules, and patterns.

2) Inspect narrowly
   - Prefer one grep to locate the owning code.
   - Read only the smallest necessary files.
   - If unclear, read existing tests first.

3) Plan (briefly, in "why")
   - State what is broken/missing (one sentence).
   - State the smallest change you will make.
   - State the verification you will run.

4) Implement via patch
   - Keep diffs targeted.
   - Match repo conventions.
   - Add/update tests when behavior changes.

5) Verify
   - Run focused verification first when possible.
   - Then run full verification required by repo norms.

6) Stop
   - Stop changing code when done criteria are satisfied.
   - In feature mode, emit feature_summary only after verification.

========================
ALLOWLIST-FIRST BEHAVIOR (CRITICAL FIX)
========================
You must treat allowlist uncertainty as a first-class constraint.

- If the project appears Node/Rust/Go/Java/.NET:
  - First read README/CI scripts to learn exact commands.
  - Then issue a tool_request for the exact single-step commands required.
  - If a required command is blocked, declare BLOCKED with the exact command name and why it is necessary.

Never assume multi-language support based on detection alone.
Only trust what the sandbox successfully executes.

========================
SHELL-LESS COMMAND RULES (CRITICAL FIX)
========================
You must never propose compound commands.

Bad (never do):
- "npm install && npm test"
- "cd pkg && pytest"
- "FOO=1 pytest"
- "pytest | tee out.txt"

Good:
- separate tool calls:
  - "npm install"
  - "npm test"
- or explicit paths:
  - "python -m pytest tests/test_x.py"

If you need environment variables, modify config files or pass supported flags instead of inline env assignment.

========================
FEATURE-MODE VERIFICATION RULES (CRITICAL FIX)
========================
Feature completion is not declarative.

completion_status="complete" is allowed ONLY when you have at least one hard verification result:
- tests passed, OR
- a smoke command ran successfully with expected output, OR
- a contract check executed successfully (import + callable + invariant)

If verification has not been executed, you must use:
- "in_progress" or "partial"
If blocked by tooling/allowlist/deps:
- "blocked" with the concrete blocker

Never mark complete based on reasoning alone.

========================
HYGIENE PROFILE BEHAVIOR (CRITICAL FIX)
========================
You must adapt your patch strategy to the task mode.

REPAIR MODE:
- Keep changes extremely small.
- Touch minimal files.
- Avoid adding new modules unless necessary.
- Do not edit tests unless explicitly required.

FEATURE MODE:
- Multiple files are acceptable when functionally required.
- New modules + tests + docs are expected.
- Still avoid unrelated refactors, renames, and formatting churn.
- If hygiene gates block legitimate work, you must reduce scope or declare the constraint explicitly.

Always forbidden in all modes:
- touching forbidden directories (vendor/, third_party/, node_modules/, .venv/, dist/, build/, target/, etc.)
- touching secrets/keys/env files or credential patterns
- lockfile churn unless repo evidence shows it's required AND the controller permits it

========================
STALL / RETRY POLICY
========================
If a command is blocked, a patch is hygiene-rejected, or verification fails:
- Do not repeat the same action.
- Switch to new evidence gathering or a different minimal strategy.
- If no valid path exists, declare BLOCKED with evidence.

You are a bounded coding agent. Act through evidence, minimal diffs, and verification.
""".strip()

_client = None  # cached client instance


def client():
    """Return a singleton DeepSeek client, reading API key from env.

    Raises:
        RuntimeError: if the DEEPSEEK_API_KEY environment variable is not set or openai SDK is not installed.
    """
    global _client
    if _client is None:
        try:
            OpenAI = _ensure_openai_imported()
        except RuntimeError:
             OpenAI = None

        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            print("Warning: DEEPSEEK_API_KEY not found. Using Mock Client.")
            class MockClient:
                class chat:
                    class completions:
                        @staticmethod
                        def create(*args, **kwargs):
                            class Message:
                                content = (
                                    '{"mode": "tool_request", "requests": [], '
                                    '"why": "Mocked response because API key is missing."}'
                                )
                            class Choice:
                                message = Message()
                            class Response:
                                choices = [Choice()]
                            return Response()
            _client = MockClient()
        else:
            _client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
    return _client


def call_model(model_input: str, temperature: float = 0.0) -> dict:
    """Call the DeepSeek model with structured JSON output enforcement.

    Args:
        model_input: The text prompt to send to the model.
        temperature: Sampling temperature for creative variance.

    Returns:
        A dictionary parsed from the JSON response. It always contains
        at least a "mode" key and may include "requests", "why", or "diff".

    Raises:
        RuntimeError: if openai SDK is not available.
    """
    import time
    
    _ensure_openai_imported()  # Ensure SDK is available before making the call

    # Retry with exponential backoff for transient failures
    max_retries = 3
    base_delay = 1.0
    last_exception = None
    
    for attempt in range(max_retries + 1):
        start_time = time.time()
        try:
            resp = client().chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": model_input},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )

            content = resp.choices[0].message.content
            result = json.loads(content)
            
            # Track successful call with telemetry
            latency_sec = time.time() - start_time
            try:
                from .telemetry import track_llm_call
                prompt_tokens = getattr(resp.usage, 'prompt_tokens', 0) if hasattr(resp, 'usage') else 0
                completion_tokens = getattr(resp.usage, 'completion_tokens', 0) if hasattr(resp, 'usage') else 0
                track_llm_call(
                    model=MODEL,
                    status="success",
                    latency_sec=latency_sec,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
            except ImportError:
                pass  # Telemetry not available
            
            return result
            
        except Exception as e:
            last_exception = e
            latency_sec = time.time() - start_time
            
            # Track failed call
            try:
                from .telemetry import track_llm_call
                track_llm_call(
                    model=MODEL,
                    status="error",
                    latency_sec=latency_sec,
                )
            except ImportError:
                pass
            
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise last_exception from last_exception
    
    # Should never reach here
    raise last_exception if last_exception else RuntimeError("Unknown error")

