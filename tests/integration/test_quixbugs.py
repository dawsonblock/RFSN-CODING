"""Integration test for QuixBugs file collection.

This test exercises the QuixBugs heuristics in the RFSN controller. It is
marked as an integration test and requires network access, as it clones
the QuixBugs repository from GitHub. The test will be skipped unless
pytest is run with the `--runslow` flag and network access is enabled via
`require_network()` from the `_netgate` module.

Instructions:
    - To run this test, set RUN_INTEGRATION=1 in the environment and ensure
      that network access is allowed.
"""

import pytest

from _netgate import require_network
from rfsn_controller.controller import _collect_relevant_files_quixbugs
from rfsn_controller.sandbox import clone_public_github, create_sandbox
from rfsn_controller.verifier import run_tests


def _run_quixbugs_file_collection() -> bool:
    """Run QuixBugs collection and return True on success."""
    sb = create_sandbox()
    # Clone QuixBugs repository
    r = clone_public_github(sb, "https://github.com/jkoppel/QuixBugs")
    if not r.get("ok"):
        return False
    # Run a failing test
    test_cmd = "pytest -q python_testcases/test_quicksort.py"
    v = run_tests(sb, test_cmd, timeout_sec=30)
    if v.ok:
        # Test passed, no bug to fix
        return True
    # Collect relevant files using QuixBugs heuristics
    tree = ["python_testcases/", "python_programs/"]
    files = _collect_relevant_files_quixbugs(sb, v, "\n".join(tree))
    expected_files = [
        "python_testcases/test_quicksort.py",
        "python_programs/quicksort.py",
    ]
    collected_paths = [f.get("path") for f in files]
    return all(ef in collected_paths for ef in expected_files)


@pytest.mark.integration
def test_quixbugs_file_collection():
    # Ensure network is available; skip otherwise
    require_network()
    assert _run_quixbugs_file_collection()
