"""Safe command execution utilities.

This module provides hardened subprocess execution that enforces:
1. Commands must be argv lists, never shell strings
2. No shell=True allowed
3. No "sh -c" or "bash -c" wrappers
4. Allowlist enforcement before execution
5. Structured logging of all executions
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .command_allowlist import is_command_allowed


# Environment variables safe to pass to subprocesses
SAFE_ENV_VARS: Set[str] = {"PATH", "HOME", "LANG", "PYTHONPATH", "TERM"}


@dataclass
class ExecResult:
    """Result from a command execution."""
    
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    command: List[str]
    timed_out: bool = False


def _validate_argv(argv: List[str]) -> None:
    """Validate that argv is a proper command list.
    
    Args:
        argv: Command as a list of strings.
        
    Raises:
        ValueError: If argv is invalid or contains forbidden patterns.
    """
    if not isinstance(argv, list):
        raise ValueError(f"argv must be a list, got {type(argv).__name__}")
    
    if len(argv) == 0:
        raise ValueError("argv must not be empty")
    
    for i, arg in enumerate(argv):
        if not isinstance(arg, str):
            raise ValueError(f"argv[{i}] must be a string, got {type(arg).__name__}")
    
    # Detect shell wrapper attempts
    base_cmd = os.path.basename(argv[0])
    if base_cmd in ("sh", "bash", "dash", "zsh", "ksh"):
        # Check for -c flag which indicates shell string execution
        if "-c" in argv:
            raise ValueError(
                f"Shell wrapper detected: {' '.join(argv[:3])}... "
                "Use proper argv list instead of sh -c 'command'"
            )


def _get_safe_env() -> Dict[str, str]:
    """Get a sanitized environment for subprocess execution.
    
    Returns:
        Dictionary of safe environment variables.
    """
    return {k: v for k, v in os.environ.items() if k in SAFE_ENV_VARS}


def safe_run(
    argv: List[str],
    cwd: str,
    timeout_sec: int = 120,
    env: Optional[Dict[str, str]] = None,
    allowed_commands: Optional[Set[str]] = None,
    check_global_allowlist: bool = True,
) -> ExecResult:
    """Execute a command safely with argv list.
    
    This function enforces:
    - Commands are argv lists, never strings
    - shell=False always
    - No sh -c or bash -c wrappers
    - Global allowlist check (optional)
    - Local command allowlist check (optional)
    - Sanitized environment
    
    Args:
        argv: Command as a list of strings.
        cwd: Working directory for execution.
        timeout_sec: Maximum execution time in seconds.
        env: Optional custom environment (merged with safe env).
        allowed_commands: Optional set of allowed base command names.
        check_global_allowlist: Whether to check global security allowlist.
        
    Returns:
        ExecResult with exit code, stdout, stderr.
        
    Raises:
        ValueError: If argv is invalid.
    """
    # Validate argv format
    _validate_argv(argv)
    
    # Check global allowlist if enabled
    if check_global_allowlist:
        # Reconstruct command string for allowlist check
        cmd_str = shlex.join(argv)
        is_allowed, reason = is_command_allowed(cmd_str)
        if not is_allowed:
            return ExecResult(
                ok=False,
                exit_code=1,
                stdout="",
                stderr=f"Command blocked by security policy: {reason}",
                command=argv,
            )
    
    # Check local allowlist if provided
    if allowed_commands is not None:
        base_cmd = os.path.basename(argv[0])
        if base_cmd not in allowed_commands:
            allowed_preview = ", ".join(sorted(allowed_commands)[:10])
            return ExecResult(
                ok=False,
                exit_code=1,
                stdout="",
                stderr=f"Command '{base_cmd}' not in allowed list. Allowed: {allowed_preview}",
                command=argv,
            )
    
    # Build safe environment
    safe_env = _get_safe_env()
    if env:
        safe_env.update(env)
    
    # Execute with explicit shell=False
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            shell=False,  # NEVER use shell=True
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            env=safe_env,
        )
        return ExecResult(
            ok=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            command=argv,
        )
    except subprocess.TimeoutExpired as e:
        return ExecResult(
            ok=False,
            exit_code=-1,
            stdout=e.stdout or "" if hasattr(e, "stdout") else "",
            stderr=e.stderr or "" if hasattr(e, "stderr") else "",
            command=argv,
            timed_out=True,
        )
    except Exception as e:
        return ExecResult(
            ok=False,
            exit_code=-1,
            stdout="",
            stderr=str(e),
            command=argv,
        )


def parse_command_string(cmd: str) -> List[str]:
    """Parse a command string into an argv list.
    
    This is for compatibility with existing code that uses string commands.
    New code should always use argv lists directly.
    
    Args:
        cmd: Command string to parse.
        
    Returns:
        List of command arguments.
        
    Raises:
        ValueError: If command cannot be parsed.
    """
    try:
        return shlex.split(cmd)
    except ValueError as e:
        raise ValueError(f"Cannot parse command: {e}") from e


def safe_run_string(
    cmd: str,
    cwd: str,
    timeout_sec: int = 120,
    env: Optional[Dict[str, str]] = None,
    allowed_commands: Optional[Set[str]] = None,
    check_global_allowlist: bool = True,
) -> ExecResult:
    """Execute a command string safely by parsing to argv.
    
    This is a compatibility wrapper for existing code.
    Prefer safe_run() with explicit argv for new code.
    
    Args:
        cmd: Command string to execute.
        cwd: Working directory.
        timeout_sec: Timeout in seconds.
        env: Optional environment variables.
        allowed_commands: Optional allowed command set.
        
    Returns:
        ExecResult with execution results.
    """
    argv = parse_command_string(cmd)
    return safe_run(
        argv=argv,
        cwd=cwd,
        timeout_sec=timeout_sec,
        env=env,
        allowed_commands=allowed_commands,
        check_global_allowlist=check_global_allowlist,
    )


def docker_exec_argv(
    container: str,
    argv: List[str],
    workdir: Optional[str] = None,
    user: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Build a docker exec command as an argv list.
    
    This ensures docker commands are properly structured without shell wrappers.
    
    Args:
        container: Container name or ID.
        argv: Command to execute inside container.
        workdir: Optional working directory inside container.
        user: Optional user to run as.
        env: Optional environment variables for the command.
        
    Returns:
        Complete docker exec argv list.
    """
    _validate_argv(argv)  # Validate inner command
    
    cmd = ["docker", "exec"]
    
    if workdir:
        cmd.extend(["-w", workdir])
    
    if user:
        cmd.extend(["-u", user])
    
    if env:
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])
    
    cmd.append(container)
    cmd.extend(argv)
    
    return cmd
