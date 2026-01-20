"""Static analysis test for command purity.

This test searches the codebase for forbidden shell execution patterns
and fails if any are found. This enforces the "no shell=True, no sh -c"
security invariant.
"""

import ast
import os
import re
from pathlib import Path
from typing import List, Set, Tuple

import pytest


# Root directory of the rfsn_controller package
PACKAGE_ROOT = Path(__file__).parent.parent / "rfsn_controller"

# Directories to exclude from scanning
EXCLUDED_DIRS: Set[str] = {
    "__pycache__",
    ".git",
    "firecracker-main",  # External dependency
    "E2B-main",  # External dependency
    "RFSN",  # External reference
}

# Files to exclude (temporary/debug scripts)
EXCLUDED_FILES: Set[str] = {
    "debug_runner.py",
}

# Forbidden patterns
FORBIDDEN_PATTERNS = [
    (r'shell\s*=\s*True', "shell=True"),
    (r'["\'](sh|bash|dash|zsh)\s+-c\b', "sh -c wrapper"),
    (r'bash\s+-lc\b', "bash -lc wrapper"),
]


def get_python_files() -> List[Path]:
    """Get all Python files in the package, excluding specified directories."""
    files = []
    for root, dirs, filenames in os.walk(PACKAGE_ROOT):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        
        for filename in filenames:
            if filename.endswith(".py") and filename not in EXCLUDED_FILES:
                files.append(Path(root) / filename)
    
    return files


def find_pattern_violations(content: str, patterns: List[Tuple[str, str]]) -> List[Tuple[int, str, str]]:
    """Find violations of forbidden patterns in file content.
    
    Args:
        content: File content to scan.
        patterns: List of (regex, description) tuples.
        
    Returns:
        List of (line_number, matched_text, pattern_description) tuples.
    """
    violations = []
    lines = content.split("\n")
    in_docstring = False
    docstring_char = None
    
    for line_num, line in enumerate(lines, start=1):
        stripped = line.strip()
        
        # Track docstrings (triple quotes)
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                docstring_char = stripped[:3]
                # Check if single-line docstring
                if stripped.count(docstring_char) >= 2:
                    continue  # Single-line docstring, skip
                in_docstring = True
                continue
        else:
            if docstring_char and docstring_char in stripped:
                in_docstring = False
                docstring_char = None
            continue
        
        # Skip comments
        if stripped.startswith("#"):
            continue
        
        for pattern, description in patterns:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                # Skip if it's in a comment at end of line
                comment_pos = line.find("#")
                if comment_pos >= 0 and match.start() > comment_pos:
                    continue
                    
                # Skip if it's explicitly setting shell=False (which is good)
                if "shell=False" in line and description == "shell=True":
                    continue
                
                violations.append((line_num, match.group(), description))
    
    return violations


def check_subprocess_calls_use_lists(content: str, filename: str) -> List[str]:
    """Use AST to verify subprocess calls use list arguments.
    
    Args:
        content: Python source code.
        filename: Name of file for error messages.
        
    Returns:
        List of error messages.
    """
    errors = []
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []  # Skip files with syntax errors
    
    for node in ast.walk(tree):
        # Check for subprocess.run, subprocess.call, subprocess.Popen
        if isinstance(node, ast.Call):
            func = node.func
            
            # Check for subprocess.run(...) style calls
            if isinstance(func, ast.Attribute):
                if func.attr in ("run", "call", "Popen", "check_call", "check_output"):
                    # Check if module is subprocess
                    if isinstance(func.value, ast.Name) and func.value.id == "subprocess":
                        # Verify first argument is a list or variable (not a string)
                        if node.args:
                            first_arg = node.args[0]
                            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                                errors.append(
                                    f"{filename}:{node.lineno}: subprocess.{func.attr}() "
                                    f"called with string argument instead of list"
                                )
                        
                        # Check for shell=True in keyword args
                        for kw in node.keywords:
                            if kw.arg == "shell":
                                if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                    errors.append(
                                        f"{filename}:{node.lineno}: subprocess.{func.attr}() "
                                        f"called with shell=True"
                                    )
    
    return errors


class TestNoShellExecution:
    """Test suite for command purity enforcement."""
    
    def test_no_forbidden_patterns_in_codebase(self) -> None:
        """Verify no forbidden shell patterns exist in the codebase."""
        all_violations = []
        
        for filepath in get_python_files():
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            violations = find_pattern_violations(content, FORBIDDEN_PATTERNS)
            
            for line_num, matched, description in violations:
                all_violations.append(
                    f"{filepath.relative_to(PACKAGE_ROOT.parent)}:{line_num}: "
                    f"Forbidden pattern '{description}': {matched}"
                )
        
        if all_violations:
            pytest.fail(
                f"Found {len(all_violations)} forbidden shell patterns:\n"
                + "\n".join(all_violations)
            )
    
    def test_subprocess_calls_use_lists(self) -> None:
        """Verify subprocess calls use list arguments, not strings."""
        all_errors = []
        
        for filepath in get_python_files():
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            errors = check_subprocess_calls_use_lists(
                content, 
                str(filepath.relative_to(PACKAGE_ROOT.parent))
            )
            all_errors.extend(errors)
        
        if all_errors:
            pytest.fail(
                f"Found {len(all_errors)} subprocess calls with string arguments:\n"
                + "\n".join(all_errors)
            )
    
    def test_exec_utils_enforces_argv_list(self) -> None:
        """Verify exec_utils.safe_run rejects non-list arguments."""
        from rfsn_controller.exec_utils import safe_run
        
        # Should raise ValueError for string input
        with pytest.raises((ValueError, TypeError)):
            safe_run("echo test", cwd="/tmp")  # type: ignore
        
        # Should raise ValueError for empty list
        with pytest.raises(ValueError):
            safe_run([], cwd="/tmp")
    
    def test_exec_utils_rejects_shell_wrappers(self) -> None:
        """Verify exec_utils rejects sh -c style wrappers."""
        from rfsn_controller.exec_utils import safe_run
        
        # Should reject sh -c
        with pytest.raises(ValueError, match="Shell wrapper detected"):
            safe_run(["sh", "-c", "echo test"], cwd="/tmp")
        
        # Should reject bash -c
        with pytest.raises(ValueError, match="Shell wrapper detected"):
            safe_run(["bash", "-c", "echo test"], cwd="/tmp")
    
    def test_safe_run_works_with_valid_argv(self) -> None:
        """Verify safe_run works with proper argv list."""
        from rfsn_controller.exec_utils import safe_run
        
        result = safe_run(
            ["echo", "hello", "world"],
            cwd="/tmp",
            check_global_allowlist=False,  # Skip allowlist for test
        )
        
        assert result.ok
        assert "hello world" in result.stdout
        assert result.exit_code == 0
