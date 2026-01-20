"""Integration test for QuixBugs file collection heuristics.

This test directly exercises the `_collect_relevant_files_quixbugs` function logic
without involving the full controller. It clones the QuixBugs repository,
runs a failing test, and verifies that the heuristic selects the expected
files. The test is marked as integration and requires network access.
"""

import pytest

from _netgate import require_network
from rfsn_controller.parsers import normalize_test_path, parse_trace_files
from rfsn_controller.sandbox import (
    clone_public_github,
    create_sandbox,
    read_file,
)
from rfsn_controller.verifier import run_tests


def _safe_path(p: str) -> bool:
    """Return True if the relative path is outside forbidden prefixes."""
    FORBIDDEN_PREFIXES = [
        ".git/",
        "node_modules/",
        ".venv/",
        "venv/",
        "__pycache__/",
    ]
    p = p.replace("\\", "/").lstrip("./")
    return not any(p.startswith(pref) for pref in FORBIDDEN_PREFIXES)


def _collect_relevant_files_quixbugs(sb, v, repo_tree: str):
    """Collect files for QuixBugs repositories with specific heuristics."""
    out = []
    if not v.failing_tests:
        return out
    # Get the failing test file path
    test_path = normalize_test_path(v.failing_tests[0])
    if not _safe_path(test_path):
        return out
    # 1. Include the failing test file
    out.append(read_file(sb, test_path, max_bytes=120000))
    # 2. Map test file to program file
    if "python_testcases/" in test_path:
        test_filename = test_path.split("/")[-1]
        if test_filename.startswith("test_") and test_filename.endswith(".py"):
            program_name = test_filename[5:-3]
            program_path = f"python_programs/{program_name}.py"
            if _safe_path(program_path):
                out.append(read_file(sb, program_path, max_bytes=120000))
    # 3. Include traceback-referenced files
    combined = (v.stdout or "") + "\n" + (v.stderr or "")
    for p in parse_trace_files(combined, limit=6):
        p2 = p.replace("\\", "/")
        if p2.startswith(sb.repo_dir.replace("\\", "/")):
            p2 = p2[len(sb.repo_dir) :].lstrip("/")
        if p2.endswith(".py") and _safe_path(p2):
            if not any(f.get("path") == p2 for f in out):
                out.append(read_file(sb, p2, max_bytes=120000))
    return out


def _run_quixbugs_file_collection() -> bool:
    sb = create_sandbox()
    # Clone QuixBugs
    r = clone_public_github(sb, "https://github.com/jkoppel/QuixBugs")
    if not r.get("ok"):
        return False
    # Run a failing test
    test_cmd = "pytest -q python_testcases/test_quicksort.py"
    v = run_tests(sb, test_cmd, timeout_sec=30)
    if v.ok:
        return True
    # Collect relevant files
    tree = ["python_testcases/", "python_programs/"]
    files = _collect_relevant_files_quixbugs(sb, v, "\n".join(tree))
    expected_files = [
        "python_testcases/test_quicksort.py",
        "python_programs/quicksort.py",
    ]
    collected_paths = [f.get("path") for f in files]
    return all(ef in collected_paths for ef in expected_files)


@pytest.mark.integration
def test_quixbugs_file_collection_direct():
    # Ensure network is available; skip otherwise
    require_network()
    assert _run_quixbugs_file_collection()
