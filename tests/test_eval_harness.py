"""Tests for the eval_harness module."""

import json
from pathlib import Path

import pytest

from rfsn_controller.eval_harness import (
    EvalMetrics,
    EvalResult,
    compare_results,
    load_eval_result,
    parse_pytest_output,
    save_eval_result,
)


class TestEvalMetrics:
    """Tests for EvalMetrics class."""
    
    def test_default_values(self) -> None:
        """Test default metric values."""
        metrics = EvalMetrics()
        
        assert metrics.tests_passed is False
        assert metrics.tests_total == 0
        assert metrics.safety_violations == 0
    
    def test_to_dict(self) -> None:
        """Test serialization."""
        metrics = EvalMetrics(
            tests_passed=True,
            tests_total=10,
            tests_failed=2,
            duration_sec=5.5,
        )
        
        d = metrics.to_dict()
        
        assert d["tests_passed"] is True
        assert d["tests_total"] == 10
        assert d["duration_sec"] == 5.5
    
    def test_from_dict(self) -> None:
        """Test deserialization."""
        data = {
            "tests_passed": True,
            "tests_total": 10,
            "tests_failed": 0,
        }
        
        metrics = EvalMetrics.from_dict(data)
        
        assert metrics.tests_passed is True
        assert metrics.tests_total == 10


class TestEvalResult:
    """Tests for EvalResult class."""
    
    def test_create_result(self) -> None:
        """Test creating evaluation result."""
        result = EvalResult(
            success=True,
            metrics=EvalMetrics(tests_passed=True, tests_total=5),
            artifacts={"events": "/path/to/events.jsonl"},
        )
        
        assert result.success is True
        assert result.timestamp  # Should be auto-generated
    
    def test_to_json(self) -> None:
        """Test JSON conversion."""
        result = EvalResult(
            success=True,
            metrics=EvalMetrics(tests_passed=True),
        )
        
        json_str = result.to_json()
        data = json.loads(json_str)
        
        assert data["success"] is True
        assert "metrics" in data
    
    def test_round_trip(self) -> None:
        """Test serialization round-trip."""
        original = EvalResult(
            success=True,
            metrics=EvalMetrics(
                tests_passed=True,
                tests_total=10,
                tests_failed=0,
                duration_sec=3.5,
            ),
            artifacts={"events": "/path/events.jsonl"},
        )
        
        d = original.to_dict()
        restored = EvalResult.from_dict(d)
        
        assert restored.success == original.success
        assert restored.metrics.tests_total == original.metrics.tests_total


class TestParsePytestOutput:
    """Tests for pytest output parsing."""
    
    def test_parse_passed_only(self) -> None:
        """Test parsing output with only passed tests."""
        output = "===== 5 passed in 0.12s ====="
        
        result = parse_pytest_output(output)
        
        assert result["passed"] == 5
        assert result["failed"] == 0
        assert result["total"] == 5
    
    def test_parse_mixed_results(self) -> None:
        """Test parsing output with mixed results."""
        output = "===== 3 passed, 2 failed, 1 skipped in 1.23s ====="
        
        result = parse_pytest_output(output)
        
        assert result["passed"] == 3
        assert result["failed"] == 2
        assert result["skipped"] == 1
        assert result["total"] == 6
    
    def test_parse_with_errors(self) -> None:
        """Test parsing output with errors."""
        output = "===== 2 passed, 1 error in 0.50s ====="
        
        result = parse_pytest_output(output)
        
        assert result["passed"] == 2
        assert result["failed"] == 1  # Errors count as failures
    
    def test_parse_empty_output(self) -> None:
        """Test parsing empty output."""
        result = parse_pytest_output("")
        
        assert result["total"] == 0


class TestSaveAndLoad:
    """Tests for save/load functions."""
    
    def test_save_and_load(self, tmp_path: Path) -> None:
        """Test saving and loading eval result."""
        result = EvalResult(
            success=True,
            metrics=EvalMetrics(tests_passed=True, tests_total=5),
        )
        
        path = tmp_path / "eval.json"
        save_eval_result(result, str(path))
        
        assert path.exists()
        
        loaded = load_eval_result(str(path))
        
        assert loaded.success == result.success
        assert loaded.metrics.tests_total == result.metrics.tests_total


class TestCompareResults:
    """Tests for result comparison."""
    
    def test_compare_improved(self) -> None:
        """Test comparing results where current is improved."""
        baseline = EvalResult(
            success=False,
            metrics=EvalMetrics(tests_passed=False, tests_failed=5),
        )
        current = EvalResult(
            success=True,
            metrics=EvalMetrics(tests_passed=True, tests_failed=0),
        )
        
        comparison = compare_results(baseline, current)
        
        assert comparison["success_changed"] is True
        assert comparison["improved"] is True
        assert comparison["failed_delta"] == -5
    
    def test_compare_regressed(self) -> None:
        """Test comparing results where current regressed."""
        baseline = EvalResult(
            success=True,
            metrics=EvalMetrics(tests_passed=True, tests_failed=0),
        )
        current = EvalResult(
            success=False,
            metrics=EvalMetrics(tests_passed=False, tests_failed=3),
        )
        
        comparison = compare_results(baseline, current)
        
        assert comparison["improved"] is False
        assert comparison["failed_delta"] == 3
