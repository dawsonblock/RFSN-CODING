"""E2B Sandbox Integration for RFSN Controller.

This module provides an optional adapter to use E2B's cloud sandboxes
instead of local Docker containers for isolated code execution.

E2B Benefits:
- Greater isolation (Firecracker microVMs)
- Scalability (cloud-hosted)
- Persistence and pause/resume capabilities
- Pre-configured templates

Usage:
    from rfsn_controller.e2b_sandbox import E2BSandboxAdapter

    # Create adapter (requires E2B_API_KEY environment variable)
    adapter = E2BSandboxAdapter()

    # Create a sandbox
    sandbox_id = await adapter.create_sandbox(template="base")

    # Run a command
    result = await adapter.run_command(sandbox_id, "pytest -q")

    # Cleanup
    await adapter.destroy_sandbox(sandbox_id)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Try to import e2b SDK - it's optional
try:
    from e2b_code_interpreter import Sandbox
    E2B_AVAILABLE = True
except ImportError:
    E2B_AVAILABLE = False
    Sandbox = None  # type: ignore


@dataclass
class E2BCommandResult:
    """Result from running a command in E2B sandbox."""

    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    sandbox_id: Optional[str] = None


@dataclass
class E2BSandboxConfig:
    """Configuration for E2B sandbox."""

    # API configuration
    api_key: Optional[str] = None

    # Sandbox settings
    template: str = "base"  # E2B template ID
    timeout_ms: int = 300_000  # 5 minutes default timeout

    # Resource limits (E2B allows up to 8 vCPUs, 8GB RAM)
    cpu_count: int = 2
    memory_mb: int = 4096

    # Metadata for tracking
    metadata: Dict[str, str] = field(default_factory=dict)


class E2BSandboxAdapter:
    """Adapter for using E2B sandboxes with RFSN Controller.

    This adapter provides a compatible interface with the local Docker
    sandbox, allowing RFSN Controller to use E2B's cloud sandboxes
    for greater isolation and scalability.
    """

    def __init__(self, config: Optional[E2BSandboxConfig] = None):
        """Initialize the E2B adapter.

        Args:
            config: E2B sandbox configuration.

        Raises:
            ImportError: If e2b SDK is not installed.
            RuntimeError: If E2B_API_KEY is not set.
        """
        if not E2B_AVAILABLE:
            raise ImportError(
                "E2B SDK not installed. Install with: pip install e2b-code-interpreter"
            )

        self.config = config or E2BSandboxConfig()

        # Get API key from config or environment
        self.api_key = self.config.api_key or os.environ.get("E2B_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "E2B_API_KEY not set. Get your API key from https://e2b.dev/dashboard"
            )

        # Track active sandboxes
        self._sandboxes: Dict[str, Any] = {}

    def create_sandbox(
        self,
        template: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Create a new E2B sandbox.

        Args:
            template: E2B template ID (default from config).
            metadata: Metadata to attach to the sandbox.

        Returns:
            Sandbox ID for subsequent operations.
        """
        template = template or self.config.template
        combined_metadata = {**self.config.metadata, **(metadata or {})}

        sandbox = Sandbox.create(
            template=template,
            metadata=combined_metadata,
            cpu_count=self.config.cpu_count,
            memory_mb=self.config.memory_mb,
        )

        sandbox_id = sandbox.sandbox_id
        self._sandboxes[sandbox_id] = sandbox

        return sandbox_id

    def run_command(
        self,
        sandbox_id: str,
        command: str,
        timeout_sec: int = 120,
        cwd: Optional[str] = None,
    ) -> E2BCommandResult:
        """Run a command in the E2B sandbox.

        Args:
            sandbox_id: The sandbox ID.
            command: Command to execute.
            timeout_sec: Timeout in seconds.
            cwd: Working directory for the command.

        Returns:
            E2BCommandResult with execution details.
        """
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            return E2BCommandResult(
                ok=False,
                exit_code=-1,
                stdout="",
                stderr=f"Sandbox {sandbox_id} not found",
                sandbox_id=sandbox_id,
            )

        try:
            # E2B provides process execution via sandbox.process
            result = sandbox.process.start_and_wait(
                command,
                timeout=timeout_sec,
                cwd=cwd or "/home/user",
            )

            return E2BCommandResult(
                ok=result.exit_code == 0,
                exit_code=result.exit_code,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                timed_out=False,
                sandbox_id=sandbox_id,
            )

        except TimeoutError:
            return E2BCommandResult(
                ok=False,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout_sec}s",
                timed_out=True,
                sandbox_id=sandbox_id,
            )
        except Exception as e:
            return E2BCommandResult(
                ok=False,
                exit_code=-1,
                stdout="",
                stderr=f"E2B execution error: {str(e)}",
                sandbox_id=sandbox_id,
            )

    def write_file(
        self,
        sandbox_id: str,
        path: str,
        content: str,
    ) -> bool:
        """Write a file to the E2B sandbox.

        Args:
            sandbox_id: The sandbox ID.
            path: Path in the sandbox.
            content: File content.

        Returns:
            True if successful.
        """
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            return False

        try:
            sandbox.filesystem.write(path, content)
            return True
        except Exception:
            return False

    def read_file(
        self,
        sandbox_id: str,
        path: str,
    ) -> Optional[str]:
        """Read a file from the E2B sandbox.

        Args:
            sandbox_id: The sandbox ID.
            path: Path in the sandbox.

        Returns:
            File content or None if failed.
        """
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            return None

        try:
            return sandbox.filesystem.read(path)
        except Exception:
            return None

    def upload_directory(
        self,
        sandbox_id: str,
        local_path: str,
        remote_path: str = "/home/user/project",
    ) -> bool:
        """Upload a local directory to the E2B sandbox.

        Args:
            sandbox_id: The sandbox ID.
            local_path: Local directory path.
            remote_path: Destination path in sandbox.

        Returns:
            True if successful.
        """
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            return False

        try:
            # Walk the directory and upload files
            import os
            for root, _, files in os.walk(local_path):
                for file in files:
                    local_file = os.path.join(root, file)
                    rel_path = os.path.relpath(local_file, local_path)
                    remote_file = os.path.join(remote_path, rel_path)

                    with open(local_file, "r") as f:
                        content = f.read()
                    sandbox.filesystem.write(remote_file, content)

            return True
        except Exception:
            return False

    def apply_patch(
        self,
        sandbox_id: str,
        diff: str,
        cwd: str = "/home/user/project",
    ) -> E2BCommandResult:
        """Apply a git patch in the E2B sandbox.

        Args:
            sandbox_id: The sandbox ID.
            diff: The unified diff to apply.
            cwd: Working directory.

        Returns:
            E2BCommandResult with apply status.
        """
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            return E2BCommandResult(
                ok=False,
                exit_code=-1,
                stdout="",
                stderr=f"Sandbox {sandbox_id} not found",
            )

        try:
            # Write diff to temp file
            diff_path = "/tmp/patch.diff"
            sandbox.filesystem.write(diff_path, diff)

            # Apply the patch
            result = sandbox.process.start_and_wait(
                f"git apply {diff_path}",
                cwd=cwd,
                timeout=60,
            )

            return E2BCommandResult(
                ok=result.exit_code == 0,
                exit_code=result.exit_code,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                sandbox_id=sandbox_id,
            )
        except Exception as e:
            return E2BCommandResult(
                ok=False,
                exit_code=-1,
                stdout="",
                stderr=f"Patch apply error: {str(e)}",
                sandbox_id=sandbox_id,
            )

    def get_sandbox_info(self, sandbox_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a sandbox.

        Args:
            sandbox_id: The sandbox ID.

        Returns:
            Sandbox info dict or None if not found.
        """
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            return None

        return {
            "sandbox_id": sandbox.sandbox_id,
            "template_id": sandbox.template_id if hasattr(sandbox, "template_id") else None,
            "is_running": sandbox_id in self._sandboxes,
        }

    def destroy_sandbox(self, sandbox_id: str) -> bool:
        """Destroy an E2B sandbox.

        Args:
            sandbox_id: The sandbox ID.

        Returns:
            True if successfully destroyed.
        """
        sandbox = self._sandboxes.pop(sandbox_id, None)
        if sandbox:
            try:
                sandbox.close()
                return True
            except Exception:
                return False
        return False

    def destroy_all(self) -> None:
        """Destroy all active sandboxes."""
        for sandbox_id in list(self._sandboxes.keys()):
            self.destroy_sandbox(sandbox_id)

    def list_sandboxes(self) -> List[str]:
        """List all active sandbox IDs.

        Returns:
            List of sandbox IDs.
        """
        return list(self._sandboxes.keys())


# Convenience function to check if E2B is available
def is_e2b_available() -> bool:
    """Check if E2B SDK is installed and API key is set.

    Returns:
        True if E2B can be used.
    """
    return E2B_AVAILABLE and bool(os.environ.get("E2B_API_KEY"))
