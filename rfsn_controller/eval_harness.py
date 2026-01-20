"""First-class evaluation harness for the RFSN controller.

This module provides standardized metrics and artifacts for measuring
controller performance across runs.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from .context import ControllerContext


@dataclass
class EvalMetrics:
    """Standardized metrics for evaluation.
    
    These metrics are machine-readable and comparable across runs.
    """
    
    # Test results
    tests_passed: bool = False
    tests_total: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    
    # Code quality
    lint_errors: int = 0
    type_errors: int = 0
    
    # Performance
    duration_sec: float = 0.0
    steps_taken: int = 0
    
    # Changes
    patch_count: int = 0
    files_touched: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    
    # Safety
    safety_violations: int = 0
    blocked_commands: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "tests_passed": self.tests_passed,
            "tests_total": self.tests_total,
            "tests_failed": self.tests_failed,
            "tests_skipped": self.tests_skipped,
            "lint_errors": self.lint_errors,
            "type_errors": self.type_errors,
            "duration_sec": round(self.duration_sec, 2),
            "steps_taken": self.steps_taken,
            "patch_count": self.patch_count,
            "files_touched": self.files_touched,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "safety_violations": self.safety_violations,
            "blocked_commands": self.blocked_commands,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvalMetrics":
        """Create from dictionary."""
        return cls(
            tests_passed=data.get("tests_passed", False),
            tests_total=data.get("tests_total", 0),
            tests_failed=data.get("tests_failed", 0),
            tests_skipped=data.get("tests_skipped", 0),
            lint_errors=data.get("lint_errors", 0),
            type_errors=data.get("type_errors", 0),
            duration_sec=data.get("duration_sec", 0.0),
            steps_taken=data.get("steps_taken", 0),
            patch_count=data.get("patch_count", 0),
            files_touched=data.get("files_touched", 0),
            lines_added=data.get("lines_added", 0),
            lines_removed=data.get("lines_removed", 0),
            safety_violations=data.get("safety_violations", 0),
            blocked_commands=data.get("blocked_commands", 0),
        )


@dataclass
class EvalResult:
    """Complete evaluation result with metrics and artifacts."""
    
    success: bool
    metrics: EvalMetrics
    artifacts: Dict[str, str] = field(default_factory=dict)
    timestamp: str = ""
    error: Optional[str] = None
    
    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "success": self.success,
            "timestamp": self.timestamp,
            "metrics": self.metrics.to_dict(),
            "artifacts": self.artifacts,
            "error": self.error,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvalResult":
        """Create from dictionary."""
        return cls(
            success=data.get("success", False),
            metrics=EvalMetrics.from_dict(data.get("metrics", {})),
            artifacts=data.get("artifacts", {}),
            timestamp=data.get("timestamp", ""),
            error=data.get("error"),
        )


def parse_pytest_output(output: str) -> Dict[str, int]:
    """Parse pytest output to extract test counts.
    
    Args:
        output: Pytest output string.
        
    Returns:
        Dict with passed, failed, skipped counts.
    """
    import re
    
    result = {"passed": 0, "failed": 0, "skipped": 0, "total": 0}
    
    # Match patterns like "5 passed, 2 failed, 1 skipped"
    patterns = [
        (r"(\d+)\s+passed", "passed"),
        (r"(\d+)\s+failed", "failed"),
        (r"(\d+)\s+skipped", "skipped"),
        (r"(\d+)\s+error", "failed"),
    ]
    
    for pattern, key in patterns:
        match = re.search(pattern, output)
        if match:
            result[key] += int(match.group(1))
    
    result["total"] = result["passed"] + result["failed"] + result["skipped"]
    
    return result


def run_eval(
    context: "ControllerContext",
    test_command: Optional[str] = None,
) -> EvalResult:
    """Run evaluation and collect metrics.
    
    Args:
        context: The controller context.
        test_command: Optional test command (defaults to config).
        
    Returns:
        EvalResult with metrics and artifacts.
    """
    from .exec_utils import safe_run_string
    
    start_time = time.time()
    test_cmd = test_command or context.config.test_command
    
    metrics = EvalMetrics()
    artifacts: Dict[str, str] = {}
    error: Optional[str] = None
    
    # Get sandbox directory
    sandbox = context.sandbox
    if sandbox is None:
        return EvalResult(
            success=False,
            metrics=metrics,
            error="No sandbox available for evaluation",
        )
    
    cwd = getattr(sandbox, "repo_dir", ".")
    
    try:
        # Run tests
        result = safe_run_string(
            test_cmd,
            cwd=cwd,
            timeout_sec=300,
            check_global_allowlist=True,
        )
        
        # Parse test output
        test_counts = parse_pytest_output(result.stdout + result.stderr)
        metrics.tests_total = test_counts["total"]
        metrics.tests_failed = test_counts["failed"]
        metrics.tests_skipped = test_counts["skipped"]
        metrics.tests_passed = test_counts["failed"] == 0 and test_counts["total"] > 0
        
        # Calculate duration
        metrics.duration_sec = time.time() - start_time
        
        # Collect artifacts
        output_dir = context.output_dir
        
        events_path = output_dir / context.config.events_file
        if events_path.exists():
            artifacts["events"] = str(events_path)
        
        plan_path = output_dir / context.config.plan_file
        if plan_path.exists():
            artifacts["plan"] = str(plan_path)
        
        # Check for JUnit XML
        junit_path = Path(cwd) / "junit.xml"
        if junit_path.exists():
            artifacts["junit"] = str(junit_path)
        
    except Exception as e:
        error = str(e)
        metrics.duration_sec = time.time() - start_time
    
    # Emit evaluation event
    context.event_log.emit(
        "evaluation_complete",
        success=metrics.tests_passed,
        tests_total=metrics.tests_total,
        tests_failed=metrics.tests_failed,
        duration_sec=metrics.duration_sec,
    )
    
    return EvalResult(
        success=metrics.tests_passed and error is None,
        metrics=metrics,
        artifacts=artifacts,
        error=error,
    )


def save_eval_result(result: EvalResult, path: str) -> None:
    """Save evaluation result to file.
    
    Args:
        result: The evaluation result.
        path: Path to save the result.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(result.to_json())


def load_eval_result(path: str) -> EvalResult:
    """Load evaluation result from file.
    
    Args:
        path: Path to the result file.
        
    Returns:
        Loaded EvalResult.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return EvalResult.from_dict(data)


def compare_results(
    baseline: EvalResult,
    current: EvalResult,
) -> Dict[str, Any]:
    """Compare two evaluation results.
    
    Args:
        baseline: The baseline result.
        current: The current result.
        
    Returns:
        Comparison dictionary with deltas.
    """
    baseline_m = baseline.metrics
    current_m = current.metrics
    
    return {
        "success_changed": current.success != baseline.success,
        "tests_delta": current_m.tests_total - baseline_m.tests_total,
        "failed_delta": current_m.tests_failed - baseline_m.tests_failed,
        "duration_delta": current_m.duration_sec - baseline_m.duration_sec,
        "improved": (
            current_m.tests_failed < baseline_m.tests_failed
            or (current_m.tests_passed and not baseline_m.tests_passed)
        ),
    }
